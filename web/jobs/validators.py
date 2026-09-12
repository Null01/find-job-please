"""Validador de contraseñas basado en zxcvbn (fortaleza real por adivinabilidad)."""
from django.core.exceptions import ValidationError

# Etiquetas para el mensaje de ayuda / error.
_LABELS = ["muy débil", "débil", "media", "fuerte", "muy fuerte"]


class ZxcvbnValidator:
    """Rechaza contraseñas cuyo score de zxcvbn sea menor a `min_score` (0–4).

    min_score=2 → rechaza "muy débil" y "débil"; exige al menos "media".
    """

    def __init__(self, min_score=2):
        self.min_score = min_score

    def validate(self, password, user=None):
        from zxcvbn import zxcvbn

        # Penaliza contraseñas que contengan datos del usuario.
        user_inputs = []
        if user is not None:
            for attr in ("email", "username", "first_name", "last_name"):
                value = getattr(user, attr, None)
                if value:
                    user_inputs.append(str(value))

        result = zxcvbn(password, user_inputs=user_inputs)
        if result["score"] < self.min_score:
            raise ValidationError(
                "La contraseña es demasiado débil o fácil de adivinar. "
                "Usa algo más largo, con variedad y sin patrones comunes.",
                code="password_too_weak",
            )

    def get_help_text(self):
        return (
            f"La contraseña debe tener al menos una seguridad "
            f"«{_LABELS[self.min_score]}» (evita patrones y palabras comunes)."
        )
