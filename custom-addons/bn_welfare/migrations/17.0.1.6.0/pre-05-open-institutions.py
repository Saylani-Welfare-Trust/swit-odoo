# -*- coding: utf-8 -*-
"""Institution applications moved from Welfare to Sadqa e Jariya. A database
still on a Welfare that handled them itself (pre_production) must have
finished them first: once upgraded, Welfare no longer shows their institution
details nor the Institution Disbursement list. Stops the upgrade (nothing is
changed) and lists the open ones."""

# finished: nothing left to do on them in Welfare
CLOSED_STATES = ('disbursed', 'reject')


def migrate(cr, version):
    if not version:
        return  # fresh install
    cr.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'welfare' AND column_name = 'institution_category'""")
    if not cr.fetchone():
        return  # this Welfare never handled institutions
    cr.execute("""SELECT w.name, w.state, p.name FROM welfare w
                    LEFT JOIN res_partner p ON p.id = w.donee_id
                   WHERE w.institution_category IS NOT NULL AND w.state NOT IN %s
                   ORDER BY w.name""", [CLOSED_STATES])
    rows = cr.fetchall()
    if rows:
        lines = '\n'.join('  %s  (%s)  %s' % (name or '-', state, donee or '-') for name, state, donee in rows)
        raise Exception(
            "bn_welfare upgrade stopped, nothing was changed: %s institution application(s) are still open "
            "in Welfare. Institutions are now handled by Sadqa e Jariya; finish them first (disburse, or "
            "Reject and Close), then upgrade again:\n%s" % (len(rows), lines))
