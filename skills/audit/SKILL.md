---
name: audit
description: Auditoría profunda de un repo con plan de fixes priorizado por criticidad. Úsalo cuando el usuario pida "haz un audit", "audita el repo", "análisis crítico" o similar — antes de tocar ningún código.
user-invocable: true
---

# /audit — Auditoría profunda + plan priorizado

Fase 1 de un contrato en dos fases (ver también `/ship` si existe, o la
implementación manual tras aprobación). **No edites nada en esta fase.**

Arguments passed: `$ARGUMENTS` (opcional: repo, rama o subcarpeta a auditar; si
está vacío, audita el repo/proyecto en el directorio de trabajo actual).

## Estado actual (automático)

```!
git branch --show-current 2>/dev/null || echo "(no es un repo git)"
git status --short 2>/dev/null | head -20
git branch -vv 2>/dev/null | grep -i "gone" || true
git worktree list 2>/dev/null
```

Usa esto como punto de partida de la sección de higiene del repo — no vuelvas
a pedir `git status`/`git branch` al usuario, ya lo tienes arriba.

## Qué revisar

1. **Correctitud:** bugs de integridad de datos, fuentes de precio/moneda
   equivocadas, target leakage en código de ML/scoring, cache stampedes o
   bugs de caché stale, condiciones de carrera.
2. **Seguridad:** credenciales/tokens filtrados en el código o el historial de
   git, secretos en `.env` committeados, endpoints sin auth.
3. **Higiene del repo:** ramas locales/remotas fusionadas sin borrar
   (`git branch -vv`, busca `[gone]`), worktrees huérfanos
   (`git worktree list`), lint no forzado en CI, tests con fake timers u
   otros patrones que cuelgan CI.
4. **Seguridad de despliegue:** modos de fallo silenciosos a mitad de deploy,
   documentación que no coincide con la realidad (verifica en vivo, no te
   fíes del README).

## Cómo verificar cada hallazgo

No especules. Para cada hallazgo candidato:
- Ejecuta el código/test real que lo demuestre (no asumas por lectura).
- Si es una rama "huérfana", confirma con `git merge-base --is-ancestor <rama> <base>`
  antes de proponer borrarla — nunca la marques huérfana solo por el `[gone]`
  de `git branch -vv` sin comprobar que de verdad está fusionada.
- Si toca datos reales del usuario, dilo explícitamente y no lo ejecutes sin permiso.

## Salida

Una tabla criticidad × alcance, en español, con estas columnas:

| Issue | Severidad (P0-P3) | Archivo:línea | Causa raíz | Fix propuesto | Autonomo / Necesita tu decisión |

- **Autónomo** = se puede arreglar sin que el usuario decida nada de negocio
  (bug claro, higiene de repo, lint, test de regresión).
- **Necesita tu decisión** = implica un trade-off de producto/negocio, cambiar
  infraestructura activa (p. ej. mover el despliegue de un proveedor a otro),
  o borrar algo no confirmado como fusionado/huérfano.

Termina con una recomendación clara de por dónde empezar, y **para ahí**:
espera confirmación antes de pasar a implementar. Si el usuario aprueba,
sigue el flujo de ramas/worktrees/CI descrito en `~/.claude/CLAUDE.md` y en el
`CLAUDE.md` del propio repo (si existe) para aplicar los fixes autónomos, uno
por rama/PR, con su test de regresión.
