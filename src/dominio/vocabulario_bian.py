"""Puente léxico español -> inglés para el dominio BIAN. Puro: solo stdlib.

Las Historias de Usuario están en español y **todo** el catálogo BIAN está en inglés (nombre,
`role_definition`, `key_features`, schemas, PUML). Eso rompe cualquier canal disperso: BM25 sobre
"notificar al cliente por correo" no recupera NADA, porque ni un término de la consulta aparece en
el corpus. No es un problema de pesos ni de IDF — es que los dos vocabularios no se tocan. El
canal denso no lo sufre porque los modelos de embeddings son multilingües, y por eso medía 0.86
frente al 0.29 del léxico.

`EQUIVALENCIAS_BASE` es el mapa que `scoring_bian` ya usaba (se movió aquí para tener un solo
sitio donde vive este vocabulario). `EQUIVALENCIAS_RETRIEVAL` lo extiende con el léxico de negocio
que aparece en las HU reales del banco.

Regla al añadir un término: la traducción es **lingüística, no de respuesta**. `correo -> mail`
es legítimo; `correo -> correspondence` sería colar la respuesta esperada en el traductor y
convertiría el benchmark en una profecía autocumplida.
"""

from __future__ import annotations

EQUIVALENCIAS_BASE: dict[str, str] = {
    "autorizar": "authorization",
    "autoriza": "authorization",
    "autorizacion": "authorization",
    "transaccion": "transaction",
    "transacciones": "transaction",
    "evaluar": "evaluate",
    "evaluacion": "evaluate",
    "actualizar": "update",
    "consultar": "retrieve",
    "recuperar": "retrieve",
    "ejecutar": "execute",
    "solicitar": "request",
    "conceder": "grant",
    "cliente": "customer",
    "cuenta": "account",
    "pago": "payment",
    "dispositivo": "device",
    "token": "token",
    "autenticar": "authentication",
    "autenticacion": "authentication",
    "activar": "activate",
    "activacion": "activate",
    "enrolar": "enroll",
    "enrolamiento": "enroll",
    "permiso": "entitlement",
    "permisos": "entitlement",
    "sesion": "session",
    "notificar": "notify",
    "notificacion": "notify",
    "auditoria": "audit",
    "fraude": "fraud",
    "riesgo": "risk",
    "factor": "factor",
}

# Extensión SOLO para recuperación (BM25). No toca el scoring, que tiene su propia regresión.
_EXTENSION_RETRIEVAL: dict[str, str] = {
    # contacto y comunicaciones
    "correo": "mail",
    "correos": "mail",
    "electronico": "electronic",
    "electronica": "electronic",
    "email": "mail",
    "mail": "mail",
    "celular": "mobile",
    "movil": "mobile",
    "telefono": "phone",
    "telefonico": "phone",
    "sms": "sms",
    "mensaje": "message",
    "mensajes": "message",
    "mensajeria": "messaging",
    "aviso": "notice",
    "alerta": "alert",
    "comunicacion": "communication",
    "comunicaciones": "communication",
    "enviar": "send",
    "envio": "send",
    "canal": "channel",
    "canales": "channel",
    # datos de parte / persona
    "datos": "data",
    "dato": "data",
    "personal": "personal",
    "personales": "personal",
    "direccion": "address",
    "domicilio": "address",
    "nombre": "name",
    "apellido": "surname",
    "identificacion": "identification",
    "documento": "document",
    "perfil": "profile",
    "contacto": "contact",
    "titular": "holder",
    "titulares": "holder",
    "representante": "representative",
    "menor": "minor",
    "menores": "minor",
    "persona": "party",
    "usuario": "user",
    "referencia": "reference",
    "directorio": "directory",
    # acciones y objetos frecuentes en las HU
    "registrar": "register",
    "registro": "register",
    "modificar": "amend",
    "cambiar": "change",
    "cambio": "change",
    "aplicar": "apply",
    "confirmar": "confirm",
    "confirmacion": "confirm",
    "validar": "validate",
    "validacion": "validate",
    "verificar": "verify",
    "verificacion": "verify",
    "mostrar": "display",
    "visualizar": "display",
    "pantalla": "screen",
    "seguridad": "security",
    "acceso": "access",
    "credencial": "credential",
    "contrasena": "password",
    "clave": "password",
    "producto": "product",
    "productos": "product",
    "servicio": "service",
    "servicios": "service",
    "contrato": "agreement",
    "solicitud": "request",
    "historial": "history",
    "estado": "status",
    "reporte": "report",
    "informe": "report",
}

EQUIVALENCIAS_RETRIEVAL: dict[str, str] = {**EQUIVALENCIAS_BASE, **_EXTENSION_RETRIEVAL}
