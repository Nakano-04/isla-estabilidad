/*
 * aux.h — Unidad de traduccion auxiliar para el experimento.
 *
 * Existe por dos motivos experimentales:
 *
 *  1. DARLE TRABAJO AL ENLAZADOR. Un programa de un solo TU no tiene
 *     funciones identicas que plegar (ICF) ni secciones muertas que
 *     eliminar (--gc-sections). Sin esto, esas palancas darian un resultado
 *     nulo trivial que no informa nada. Aqui se incluyen deliberadamente:
 *       - tres funciones NOINLINE con cuerpo IDENTICO (candidatas a ICF)
 *       - una funcion nunca referenciada (candidata a --gc-sections)
 *
 *  2. SEPARAR LA EJECUCION DE LA OPTIMIZACION INTERNA. Las tres funciones
 *     identicas existen para que el optimizador no las desaparezca al
 *     inlinarlas: si se inlinean, el ICF se queda sin objetivo.
 */

#ifndef ISLA_AUX_H
#define ISLA_AUX_H

#include <stdint.h>

#if defined(_MSC_VER)
#  define ISLA_NOINLINE __declspec(noinline)
#else
#  define ISLA_NOINLINE __attribute__((noinline))
#endif

/* Las tres siguientes tienen cuerpos byte a byte identicos. */
ISLA_NOINLINE uint32_t aux_cala1(uint32_t x);
ISLA_NOINLINE uint32_t aux_cala2(uint32_t x);
ISLA_NOINLINE uint32_t aux_cala3(uint32_t x);

/* Cuerpo distinto: NO debe ser plegada por ICF. */
ISLA_NOINLINE uint32_t aux_mix(uint32_t x);

/* Nunca referenciada: candidata a eliminacion por --gc-sections. */
uint32_t aux_no_usada(uint32_t x);

#endif /* ISLA_AUX_H */
