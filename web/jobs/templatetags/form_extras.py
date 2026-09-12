from django import template

register = template.Library()


@register.simple_tag
def form_errors(form):
    """Devuelve todos los errores del form (no-field + de campos) en una lista única."""
    errors = list(form.non_field_errors())
    for field in form:
        errors.extend(field.errors)
    # Sin duplicados, conservando el orden.
    seen, out = set(), []
    for e in errors:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out
