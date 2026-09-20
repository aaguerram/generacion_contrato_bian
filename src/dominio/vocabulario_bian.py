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


# ── Puente hacia los NOMBRES DE CLASE del BOM (`entidades_bian`) ──────────────────────────────
# Dos diferencias con el mapa de arriba, y conviene no mezclarlas:
#
# 1. Es 1:N. El corpus del BOM escribe `eMail Address` y `Cell/Phone Number`, así que `correo ->
#    mail` no empareja con nada: hacen falta las DOS formas. Medido sobre el caso E2E 1, sin esto
#    el dueño real (`Party Reference Data Directory`) cae del puesto 1 al 8.
# 2. Algunas entradas no son traducción lingüística sino **el nombre de la clase con la que BIAN
#    modela ese concepto**: un cliente, un usuario o un menor son todos un `Party`. Es la misma
#    inferencia que hace un modelador ("si represento a un cliente, uso Party"), y sin ella el
#    canal no encuentra al propietario. Sigue sin colar la respuesta: nombra una CLASE del modelo,
#    nunca un Service Domain.
# Frases del negocio que en BIAN son UNA cosa distinta de sus palabras. "datos de contacto" no es
# "contact" (que en el BOM es el centro de contacto: Customer Contact, Contact Handler) sino
# Contact Point + las clases *Address (Electronic/Phone/Postal Address). Se resuelven ANTES de
# tokenizar palabra a palabra y la frase se retira del texto, así `contact` no entra por ella.
# Medido 2026-09-20 (E2E 1): con "contacto" -> contact, Contact Handler era el #1 del canal en
# todas las corridas y entraba a 2b sin tener nada que ver con la historia.
FRASES_BOM_POR_TERMINO: dict[str, set[str]] = {
    "datos de contacto": {"point", "address", "electronic", "phone", "postal"},
    "informacion de contacto": {"point", "address", "electronic", "phone", "postal"},
    "medios de contacto": {"point", "address", "electronic", "phone", "postal"},
    "punto de contacto": {"contact", "point"},
    "correo electronico": {"electronic", "address", "email"},
    # Sin `number`: es un token genérico del BOM (Card Number, Account Number, PaymentCardType...)
    # y medido (E2E 1, 2026-09-20) metió tres SD de tarjetas como propietarios "del celular".
    "numero celular": {"phone", "mobile", "cell"},
    "numero de celular": {"phone", "mobile", "cell"},
    "telefono celular": {"phone", "mobile", "cell"},
    "telefono movil": {"phone", "mobile"},
}

CLASES_BOM_POR_TERMINO: dict[str, set[str]] = {
    # contacto: las dos formas que usa el corpus
    "correo": {"email", "mail"},
    "correos": {"email", "mail"},
    "email": {"email", "mail"},
    "celular": {"cell", "phone", "mobile"},
    "movil": {"mobile", "phone", "cell"},
    "telefono": {"phone", "telephone"},
    "telefonico": {"phone", "telephone"},
    "direccion": {"address"},
    "domicilio": {"address", "residential"},
    # "datos de contacto" en BIAN son Contact Point + *Address (Electronic/Phone/Postal Address):
    # sin `address`, "contacto" solo llegaba a las clases del CENTRO de contacto (Customer Contact).
    "contacto": {"contact", "address"},
    "contactos": {"contact", "address"},
    # la parte -> la clase Party
    "cliente": {"customer", "party"},
    "clientes": {"customer", "party"},
    "usuario": {"user", "party"},
    "usuarios": {"user", "party"},
    "persona": {"person", "party"},
    "personas": {"person", "party"},
    "menor": {"minor", "party"},
    "menores": {"minor", "party"},
    "tutor": {"guardian", "party"},
    "titular": {"holder", "party"},
    "representante": {"representative", "party"},
    # comunicaciones
    "notificar": {"notification", "notify"},
    "notificacion": {"notification", "notify"},
    "notificaciones": {"notification", "notify"},
    "enviar": {"send", "outbound", "delivery"},
    "envio": {"send", "outbound", "delivery"},
}
