def camel_key(field_name):
    """Portal form key of a snake_case field name: count_non_residential -> countNonResidential"""
    first, *rest = field_name.split('_')
    return first + ''.join(part[:1].upper() + part[1:] for part in rest)
