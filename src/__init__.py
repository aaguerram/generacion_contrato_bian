"""Validación de BIAN Service Domains — arquitectura hexagonal.

    dominio        reglas puras (normalización, modelos)
    aplicacion     caso de uso + puertos (grafo LangGraph)
    adaptadores    entrada/ (CLI) · salida/ (catálogo JSON, RAG vectorial, LLM, persistencia)
    configuracion  settings · observabilidad (LangSmith) · composition root

Ver ARQUITECTURA.md.
"""

__version__ = "0.1.0"
