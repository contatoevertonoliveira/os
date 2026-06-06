from __future__ import annotations

from django.shortcuts import render


def permission_denied(request, exception=None):
    """
    Handler 403 amigável (mantém a skin do site).
    """
    return render(
        request,
        "403.html",
        {
            "title": "Acesso negado",
            "message": "Você não tem permissão para acessar essa página. Entre em contato com seu gerente!",
        },
        status=403,
    )

