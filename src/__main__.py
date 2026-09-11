import sys

_SUBCOMANDOS_MAPEO = {"mapear-historias", "mapear_historias", "map-historias"}

if len(sys.argv) > 1 and sys.argv[1] in _SUBCOMANDOS_MAPEO:
    from src.adaptadores.entrada.cli_mapeo import main

    raise SystemExit(main(sys.argv[2:]))

from src.adaptadores.entrada.cli import main

raise SystemExit(main())
