from odoo import _, api, models
from odoo.exceptions import ValidationError


class ApprovalEngine(models.AbstractModel):
    """Shared approval service. All methods are private (underscore) so they cannot
    be called through RPC; the gate calls them from the protected button."""

    _name = "approval.engine"
    _description = "Approval Engine"

    @api.model
    def _department_wise(self):
        """Department scoping is active only when both the master and department switches are on."""
        params = self.env["ir.config_parameter"].sudo()
        return (params.get_param("approval_cycle.enabled") == "True"
                and params.get_param("approval_cycle.department_wise") == "True")

    # (amount field, currency fields tried in order). Expense reports store the
    # company-currency total separately from the line currency.
    _AMOUNT_SOURCES = (
        ("amount_total", ("currency_id",)),
        ("total_amount", ("company_currency_id", "currency_id")),
        ("amount", ("currency_id",)),
    )

    @api.model
    def _raw_amount(self, record):
        """(amount, currency) of the document in its own currency."""
        company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
        if record._name == "mrp.production" and "product_id" in record._fields and record.product_id:
            cost = record.product_id.with_company(company).standard_price or 0.0
            return (record.product_qty or 0.0) * cost, company.currency_id
        for amount_field, currency_fields in self._AMOUNT_SOURCES:
            if amount_field not in record._fields:
                continue
            amount = record[amount_field] or 0.0
            currency = False
            for fname in currency_fields:
                if fname in record._fields and record[fname]:
                    currency = record[fname]
                    break
            return amount, currency or company.currency_id
        return 0.0, company.currency_id

    @api.model
    def _requests(self, record, state, method_name):
        return self.env["approval.request"].sudo().search([
            ("model_name", "=", record._name),
            ("res_id", "=", record.id),
            ("method_name", "=", method_name),
            ("state", "=", state),
        ], order="id desc")

    @api.model
    def _find_rule(self, record, method_name, user=None):
        """First matching rule for this document and button.

        ``user`` is the person the department check is based on. A manager
        resubmitting someone else's request must still match that person's
        department, not the manager's.
        """
        if self.env["ir.config_parameter"].sudo().get_param("approval_cycle.enabled") != "True":
            return self.env["approval.rule"]
        user = user or self.env.user
        company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
        domain = [
            ("active", "=", True),
            ("model_name", "=", record._name),
            ("method_name", "=", method_name),
            "|", ("company_id", "=", False), ("company_id", "=", company.id),
        ]
        rules = self.env["approval.rule"].sudo().search(domain, order="sequence, id")
        for rule in rules:
            if rule._matches(record, user=user):
                return rule
        return self.env["approval.rule"]

    @api.model
    def _eligible_approvers(self, line, requester, department, company, department_wise):
        """Users who can approve this user or group stage. Raises when none can."""
        role = line.role_id
        if not role.active:
            raise ValidationError(_("Role '%s' is inactive but is used by this rule.", role.display_name))
        if role.same_department_only:
            if not department_wise:
                raise ValidationError(_(
                    "Role '%s' depends on departments, but Department-wise Approval is switched off in Settings.",
                    role.display_name))
            if not department:
                raise ValidationError(_(
                    "Role '%(role)s' needs a department, but %(user)s has no department on their employee record.",
                    role=role.display_name, user=requester.display_name))
        approvers = role._resolve_approvers(company, department)
        if not line.allow_requester:
            approvers -= requester
        if not approvers:
            raise ValidationError(_("No eligible approver is configured for role '%s'.", role.display_name))
        if len(approvers) < line.required_approvals:
            raise ValidationError(_(
                "Role '%(role)s' has %(count)s eligible approver(s) but the stage requires %(required)s approvals.",
                role=role.display_name, count=len(approvers), required=line.required_approvals))
        return approvers

    @api.model
    def _manager_chain(self, department, company, requester, allow_requester, escalate):
        """[(department, manager user)] from the requester's department toward the root.

        One entry per distinct manager. Parent levels are included only when
        ``escalate`` is set. A manager who is the requester is skipped unless the
        stage allows it, and the walk continues to the parent.
        """
        found = []
        seen = set()
        dept = department.sudo() if department else self.env["hr.department"]
        while dept:
            user = dept.manager_id.user_id
            eligible = bool(
                user and user.active and not user.share
                and (not company or company in user.company_ids)
                and (allow_requester or user != requester)
            )
            if eligible and user.id not in seen:
                found.append((dept, user))
                seen.add(user.id)
                if not escalate:
                    break
            dept = dept.parent_id
        return found

    @api.model
    def _approval_steps(self, record, rule, requester, department, company, department_wise):
        """Concrete approval steps for this document, in the order they must be asked.

        A department-manager stage becomes one step per manager up the tree when
        that role includes parent departments. CFO, COO, and other user or group
        roles stay a single step.
        """
        steps = []
        for line in rule._applicable_lines(record):
            role = line.role_id
            if role.approver_type == "department_manager":
                if line.required_approvals > 1:
                    raise ValidationError(_(
                        "Role '%s' has one manager per department, so the stage cannot require more than one approval.",
                        role.display_name))
                if not department_wise:
                    raise ValidationError(_(
                        "Role '%s' depends on departments, but Department-wise Approval is switched off in Settings.",
                        role.display_name))
                if not department:
                    raise ValidationError(_(
                        "Role '%(role)s' needs a department, but %(user)s has no department on their employee record.",
                        role=role.display_name, user=requester.display_name))
                chain = self._manager_chain(
                    department, company, requester, line.allow_requester, role.escalate_to_parents)
                if not chain:
                    raise ValidationError(_("No department manager is available for role '%s'.", role.display_name))
                for dept, user in chain:
                    steps.append({
                        "line": line,
                        "approvers": user,
                        "approval_department": dept,
                        "required": 1,
                        "allow_requester": line.allow_requester,
                    })
            else:
                approvers = self._eligible_approvers(line, requester, department, company, department_wise)
                steps.append({
                    "line": line,
                    "approvers": approvers,
                    "approval_department": self.env["hr.department"],
                    "required": line.required_approvals,
                    "allow_requester": line.allow_requester,
                })
        return steps

    @api.model
    def _create_request(self, record, rule, requester=None, previous=None, step=None):
        """Create a request for one step. The first call checks the whole chain."""
        requester = requester or self.env.user
        department_wise = self._department_wise()
        if previous and previous.department_id:
            department = previous.department_id
        else:
            department = requester.sudo().employee_id.department_id if department_wise else self.env["hr.department"]
        company = record.company_id if "company_id" in record._fields and record.company_id else self.env.company
        if step is None:
            steps = self._approval_steps(record, rule, requester, department, company, department_wise)
            if not steps:
                raise ValidationError(_("No approval stage of rule '%s' applies to this document.", rule.name))
            step = steps[0]
        approvers = step["approvers"]
        approval_department = step["approval_department"]
        self.env.ref("bn_approval_cycle.group_approval_user").sudo().write(
            {"users": [(4, user.id) for user in approvers]})
        amount, currency = self._raw_amount(record)
        request = self.env["approval.request"].sudo().create({
            "rule_id": rule.id,
            "previous_request_id": previous.id if previous else False,
            "model_name": record._name,
            "res_id": record.id,
            "document_name": record.display_name,
            "requester_id": requester.id,
            "department_id": department.id if department else False,
            "approval_department_id": approval_department.id if approval_department else False,
            "company_id": company.id,
            "amount": amount,
            "currency_id": currency.id,
            "method_name": rule.method_name,
            "stage_ids": [(0, 0, {
                "sequence": step["line"].sequence,
                "rule_line_id": step["line"].id,
                "role_id": step["line"].role_id.id,
                "approver_ids": [(6, 0, approvers.ids)],
                "required_approvals": step["required"],
                "allow_requester": step["allow_requester"],
                "state": "pending",
            })],
        })
        request.current_stage_id = request.stage_ids[:1]
        if approval_department:
            body = _("Approval requested from the manager of %s.", approval_department.name)
        else:
            body = _("Approval requested for %s.", record.display_name)
        request.message_post(body=body)
        if hasattr(record, "message_post"):
            record.sudo().message_post(body=_("%(body)s (%(name)s)", body=body, name=request.name))
        request.stage_ids._schedule_activities()
        return request

    @api.model
    def _gate(self, records, method_name):
        """Split ``records`` into those allowed to run the button now and an
        action opening the approval request(s) for the others.

        Returns ``(allowed_records, action_or_False)``. Requests are created
        and committed (no exception is raised) so the approvers can see them."""
        records = records.exists()
        allowed = records.browse()
        blocked = self.env["approval.request"]
        for record in records:
            # 1. A request is pending (even if the feature was switched off since).
            # Checked before an earlier approved stage, so a later stage still blocks.
            pending = self._requests(record, "pending", method_name)[:1]
            if pending:
                if not pending._document_changed():
                    blocked |= pending
                    continue
                pending._cancel_internal(_("The document was modified while pending; request cancelled."))
            # 2. Already approved and not executed yet: let it through (unless modified).
            approved = self._requests(record, "approved", method_name).filtered(lambda r: not r.executed)[:1]
            if approved:
                if not approved._document_changed():
                    allowed |= record
                    continue
                approved._cancel_internal(_("The document was modified after approval; approval withdrawn."))
            # 3. Does a rule require approval?
            rule = self._find_rule(record, method_name)
            if rule:
                blocked |= self._create_request(record, rule)
            else:
                allowed |= record
        action = False
        if blocked:
            action = {
                "type": "ir.actions.act_window",
                "name": _("Approval Request"),
                "res_model": "approval.request",
                "view_mode": "form" if len(blocked) == 1 else "tree,form",
                "target": "current",
            }
            if len(blocked) == 1:
                action["res_id"] = blocked.id
            else:
                action["domain"] = [("id", "in", blocked.ids)]
        return allowed, action

    @api.model
    def _consume(self, records, result, method_name):
        """Mark approvals as executed once the button really finished
        (a returned wizard action means it is not finished yet)."""
        if isinstance(result, dict):
            return
        for record in records:
            for request in self._requests(record, "approved", method_name).filtered(lambda r: not r.executed):
                request.write({"executed": True})
                request.message_post(body=_("The approved button was executed."))
