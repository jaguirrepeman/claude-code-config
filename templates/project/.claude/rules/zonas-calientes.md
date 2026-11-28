---
paths:
  - "backend/app/services/**/*.py"
---

# Zona caliente: cálculo

Estos ficheros son zona caliente: un error aquí no rompe el build, cambia un número que alguien
va a mirar. Lo que eso implica, además de lo que ya dice `CLAUDE.md`:

- Plan escrito antes de tocar nada (criterio, ficheros, qué no se toca), y se ejecuta sin
  esperar salvo que toque una base de datos o cambie el comportamiento de forma radical (ver
  "Autonomía" en ~/.claude/CLAUDE.md).
- Test de regresión que fije el número esperado (el criterio lo da la persona, no el código
  actual), visto fallar antes del cambio y pasar después.
- Antes de dar el cambio por bueno, `/refute` con el criterio de aceptación: una segunda opinión
  en contexto limpio que intenta refutarlo y devuelve pruebas.
- Un refactor no mueve ni un céntimo: si una cifra de salida cambia, se revierte primero y se
  investiga después.
