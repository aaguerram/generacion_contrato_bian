"""Ensambla docs/BIAN_Service_Landscape_V14.0_Matrix_View.es.json.

No traduce nada: toma las traducciones que Claude escribio a mano en es_*.json y las aplica
sobre una copia del landscape original. `documentation` se REGENERA a partir de los cuatro
campos ya traducidos (es el render de esos campos, no una fuente aparte) con los marcadores
en espanol -- `_limpiar_documentacion` (src/dominio/modelos.py:29) captura cualquier `** ... **`,
asi que traducir la etiqueta es seguro.

Intactos a proposito: name, *_url, functional_pattern, asset_type, generic_artifact_type,
control_record, registration_status, bom_diagram, control_record_diagram. Son identificadores
BIAN y claves de join del pipeline (anclaje por nombre normalizado, parent_control_record).
"""
import json, pathlib, re, sys, copy

BASE = pathlib.Path('docs/BIAN_Service_Landscape_V14.0_Matrix_View.json')
DESTINO = pathlib.Path('docs/BIAN_Service_Landscape_V14.0_Matrix_View.es.json')
TRAD = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
CAMPOS = ['role_definition', 'example_of_use', 'executive_summary', 'key_features']
MARCA = {'role_definition': '** 1. Rol **', 'example_of_use': '** 2. Ejemplos de uso **',
         'executive_summary': '** 3.Resumen ejecutivo **', 'key_features': '** 4. Caracteristicas clave **'}
GC = '** Comentario general **'


def recorrer(d):
    sds, doms = [], []
    def rec(bd):
        doms.append(bd)
        sds.extend(bd.get('service_domains', []) or [])
        for h in bd.get('business_domains', []) or []:
            rec(h)
    for ba in d['business_areas']:
        for bd in ba.get('business_domains', []) or []:
            rec(bd)
    return sds, doms


def render(sd):
    partes = [f"{MARCA[c]}\n{sd.get(c) or ''}" for c in CAMPOS]
    g = sd.get('_general_comment') or ''
    return "\n\n".join(partes) + f"\n\n{GC}" + (f"\n{g}" if g.strip() else "")


def main():
    original = json.load(open(BASE, encoding='utf-8'))
    nuevo = copy.deepcopy(original)
    trad = {}
    for p in sorted(TRAD.glob('es_[0-9]*.json')):
        trad.update(json.load(open(p, encoding='utf-8')))
    tax = json.load(open(TRAD / 'es_tax.json', encoding='utf-8')) if (TRAD / 'es_tax.json').exists() else {'areas': {}, 'dominios': {}}

    sds_o, _ = recorrer(original)
    sds_n, doms_n = recorrer(nuevo)
    faltan, problemas = [], []

    for orig, sd in zip(sds_o, sds_n):
        t = trad.get(sd['name'])
        if t is None:
            faltan.append(sd['name']); continue
        for c in CAMPOS:
            if orig.get(c):
                if not t.get(c):
                    problemas.append(f"{sd['name']}: falta {c}")
                else:
                    sd[c] = t[c]
        if t.get('general_comment'):
            sd['_general_comment'] = t['general_comment']
        if orig.get('documentation'):
            sd['documentation'] = render(sd)
        sd.pop('_general_comment', None)

    for ba in nuevo['business_areas']:
        if ba.get('documentation') and tax['areas'].get(ba['name']):
            ba['documentation'] = tax['areas'][ba['name']]
        elif ba.get('documentation'):
            problemas.append(f"area sin traducir: {ba['name']}")
    for bd in doms_n:
        if bd.get('documentation') and tax['dominios'].get(bd['name']):
            bd['documentation'] = tax['dominios'][bd['name']]
        elif bd.get('documentation'):
            problemas.append(f"dominio sin traducir: {bd['name']}")

    nuevo['idioma'] = 'es'
    nuevo['traduccion'] = {
        'de': 'en', 'a': 'es', 'fecha': '2026-09-17', 'traductor': 'Claude Opus 5 (manual, sin script)',
        'fuente': str(BASE), 'respaldo': 'docs/_respaldo/BIAN_Service_Landscape_V14.0_Matrix_View.en.2026-09-17.json',
        'campos_traducidos': CAMPOS + ['documentation (regenerado)', 'business_area.documentation', 'business_domain.documentation'],
        'campos_intactos': ['name', 'object_url', 'sd_overview_url', 'functional_pattern', 'asset_type',
                            'generic_artifact_type', 'control_record', 'registration_status',
                            'bom_diagram', 'control_record_diagram'],
        'nota': 'Texto derivado por traduccion automatica asistida: vale como INDICE de recuperacion, '
                'NO como evidencia BIAN. La evidencia sigue siendo el archivo en ingles.',
    }
    print(f"SD: {len(sds_n)} | traducidos: {len(sds_n)-len(faltan)} | sin traducir: {len(faltan)}")
    if faltan:
        print("  faltan:", ", ".join(faltan[:12]), "..." if len(faltan) > 12 else "")
    if problemas:
        print(f"  problemas ({len(problemas)}):", *problemas[:12], sep="\n    ")
    if not faltan and not problemas:
        DESTINO.write_text(json.dumps(nuevo, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"\nESCRITO {DESTINO} ({DESTINO.stat().st_size} bytes)")
    else:
        print("\nNO se escribe el destino hasta que no falte nada.")


main()
