import random
import math
import pandas as pd
from collections import deque


class SimulacionGuardiaOdontologica:

    LIBRE         = "L"
    ATENDIENDO    = "A"
    ESTERILIZANDO = "E"

    def __init__(self, params):
        p = params
        self.media_llegada         = float(p.get("media_llegada", 30))
        self.tiempo_triage         = float(p.get("tiempo_triage", 5))
        self.prob_odontologo       = 0.70
        self.prob_retiro           = 0.40
        self.media_odontologo      = float(p.get("media_odontologo", 30))
        self.uniforme_a            = float(p.get("uniforme_a", 40))
        self.uniforme_b            = float(p.get("uniforme_b", 60))
        self.tiempo_paciencia      = float(p.get("tiempo_paciencia", 30))
        self.pac_para_esterilizar  = int(p.get("pacientes_esterilizar", 3))
        self.tiempo_esterilizacion = float(p.get("tiempo_esterilizacion", 15))
        self.max_iter              = int(p.get("max_iteraciones", 100000))
        self.tiempo_max            = float(p.get("tiempo_max", 480))
        self.j_hora                = float(p.get("inicio_mostrar", 0))
        self.cant_mostrar          = int(p.get("cant_mostrar", 100))

        self.filas        = []
        self.ultima_fila  = None
        self.estadisticas = {}

    # ── VA ────────────────────────────────────────────────────────────────
    def _exp_neg(self, media):
        """−media · ln(1 − RND)  — RND se redondea a 2 decimales antes del calculo.
        Se limita a 0.99 para evitar log(0) cuando random() redondea a 1.00."""
        rnd = min(round(random.random(), 2), 0.99)
        return rnd, -media * math.log(1.0 - rnd)

    def _uniforme(self, a, b):
        """A + RND · (B − A)  — RND se redondea a 2 decimales antes del calculo"""
        rnd = round(random.random(), 2)
        return rnd, a + rnd * (b - a)

    # ── Simulacion ────────────────────────────────────────────────────────
    def simular(self):
        INF       = float("inf")
        clock     = 0.0
        iteracion = -1

        # ── Control de ventana de captura [j_hora, j_hora+i_max) ──────────
        j_hora     = self.j_hora   # hora decimal (inicio_mostrar)
        i_max      = self.cant_mostrar
        _n_guardadas = [0]         # contador mutable para la closure

        def _maybe_save(fila):
            """Guarda la fila solo si cae en la ventana y no llenamos i_max.
               La fila 0 (iteracion==0) se trata especialmente: siempre se
               incluye si hora>=j pero NO gasta el cupo de i_max."""
            it = fila["iteracion"]
            h  = fila["hora"]
            if h < j_hora:
                return   # antes de la ventana, descartar
            if it == 0:
                self.filas.append(fila)
                return   # fila 0 no gasta cupo
            if _n_guardadas[0] < i_max:
                self.filas.append(fila)
                _n_guardadas[0] += 1

        rnd_ll0, t_ll0 = self._exp_neg(self.media_llegada)
        prox_llegada            = t_ll0
        prox_fin_triage         = INF
        prox_fin_esper_od       = INF
        prox_fin_esper_cir      = INF
        prox_fin_odontologo     = INF
        prox_fin_cirujano       = INF
        prox_fin_esterilizacion = INF

        # Objetos permanentes
        triage_estado      = self.LIBRE
        triage_cola        = 0
        od_estado          = self.LIBRE
        od_cola            = 0
        od_contador_acepta = 0
        cir_estado         = self.LIBRE
        cir_cola           = 0
        cir_atendidos      = 0
        cir_contador_pac   = 0

        # Acumuladores
        # Invariante: acum_libre + acum_atiende + acum_esteril == clock
        acum_libre_cirujano      = 0.0
        acum_atiende_cirujano    = 0.0
        acum_esteriliza_cirujano = 0.0
        cnt_llegadas             = 0
        cnt_retirados            = 0
        acum_espera_odontologo   = 0.0
        cnt_acepta_od            = 0

        # Colas FIFO
        cola_triage = deque()
        cola_od     = deque()
        cola_cir    = deque()

        pacientes = {}
        id_pac    = 0

        def nuevo_id():
            nonlocal id_pac
            id_pac += 1
            return id_pac

        def prox_evento():
            # Comparacion explicita de floats: evita el warning del linter con min(dict)
            t_min = prox_llegada
            ev    = "llegada_paciente"
            if prox_fin_triage         < t_min: t_min = prox_fin_triage;         ev = "fin_triage"
            if prox_fin_esper_od       < t_min: t_min = prox_fin_esper_od;       ev = "fin_espera_en_cola_odontologo"
            if prox_fin_esper_cir      < t_min: t_min = prox_fin_esper_cir;      ev = "fin_espera_en_cola_cirujano"
            if prox_fin_odontologo     < t_min: t_min = prox_fin_odontologo;     ev = "fin_odontologo"
            if prox_fin_cirujano       < t_min: t_min = prox_fin_cirujano;       ev = "fin_cirujano"
            if prox_fin_esterilizacion < t_min: t_min = prox_fin_esterilizacion; ev = "fin_esterilizacion"
            return ev, t_min

        def _recalc_fin_esper_od():
            nonlocal prox_fin_esper_od
            for p in cola_od:
                if p.get("timer_activo"):
                    prox_fin_esper_od = p["fin_espera"]
                    return
            prox_fin_esper_od = INF

        def _recalc_fin_esper_cir():
            nonlocal prox_fin_esper_cir
            for p in cola_cir:
                if p.get("timer_activo"):
                    prox_fin_esper_cir = p["fin_espera"]
                    return
            prox_fin_esper_cir = INF

        # ── Snapshot ──────────────────────────────────────────────────────
        def snapshot(evento_nombre,
                     rnd_ll=None,    t_ll=None,
                     rnd_deriv=None, derivado_a=None,
                     t_triage=None,
                     rnd_od=None,    t_od=None,
                     rnd_cir=None,   t_cir=None,
                     t_paciencia_od=None, t_paciencia_cir=None,
                     rnd_retiro=None, retiro_si_no=None,
                     pac_id=None,
                     _incrementar=True):
            nonlocal iteracion
            if _incrementar:
                iteracion += 1

            # Redondear acumuladores a 2 dec antes de calcular % 
            # -> coherencia entre valor mostrado en columna y porcentaje mostrado
            _libre_r   = round(acum_libre_cirujano,      2)
            _atiende_r = round(acum_atiende_cirujano,    2)
            _esteril_r = round(acum_esteriliza_cirujano, 2)
            acum_trabaja = round(_libre_r + _atiende_r + _esteril_r, 2)

            pct_at = round(_atiende_r / acum_trabaja * 100, 2) if acum_trabaja else 0
            pct_es = round(_esteril_r / acum_trabaja * 100, 2) if acum_trabaja else 0
            pct_oc = round(pct_at + pct_es, 2)

            pct_ret     = round(cnt_retirados / cnt_llegadas * 100, 2) if cnt_llegadas else 0
            prom_esp_od = round(round(acum_espera_odontologo, 2) / cnt_acepta_od, 2) if cnt_acepta_od else 0

            hora = round(clock / 60, 2)
            dia  = int(clock // (24 * 60)) + 1

            t_esteril_fila = (round(self.tiempo_esterilizacion, 2)
                              if evento_nombre == "fin_cirujano"
                              and (cir_atendidos % self.pac_para_esterilizar == 0)
                              else "-")

            return {
                "iteracion":  iteracion,
                "dia":        dia,
                "hora":       hora,
                "clock":      round(clock, 2),
                "evento":              evento_nombre,
                "rnd_llegada":         round(rnd_ll, 2)    if rnd_ll    is not None else "-",
                "t_entre_llegadas":    round(t_ll, 2)      if t_ll      is not None else "-",
                "prox_llegada":        round(prox_llegada, 2)            if prox_llegada            < INF else "-",
                "t_triage":            round(t_triage, 2)  if t_triage  is not None else "-",
                "prox_fin_triage":     round(prox_fin_triage, 2)         if prox_fin_triage         < INF else "-",
                "t_paciencia_od":      round(t_paciencia_od, 2)  if t_paciencia_od  is not None else "-",
                "prox_fin_esper_od":   round(prox_fin_esper_od, 2)       if prox_fin_esper_od       < INF else "-",
                "t_paciencia_cir":     round(t_paciencia_cir, 2) if t_paciencia_cir is not None else "-",
                "prox_fin_esper_cir":  round(prox_fin_esper_cir, 2)      if prox_fin_esper_cir      < INF else "-",
                "rnd_odontologo":      round(rnd_od, 2)    if rnd_od    is not None else "-",
                "t_atencion_od":       round(t_od, 2)      if t_od      is not None else "-",
                "prox_fin_odontologo": round(prox_fin_odontologo, 2)     if prox_fin_odontologo     < INF else "-",
                "rnd_cirujano":        round(rnd_cir, 2)   if rnd_cir   is not None else "-",
                "t_atencion_cir":      round(t_cir, 2)     if t_cir     is not None else "-",
                "prox_fin_cirujano":   round(prox_fin_cirujano, 2)       if prox_fin_cirujano       < INF else "-",
                "t_esterilizacion":    t_esteril_fila,
                "prox_fin_esteril":    round(prox_fin_esterilizacion, 2) if prox_fin_esterilizacion < INF else "-",
                "rnd_deriv":           round(rnd_deriv, 2) if rnd_deriv is not None else "-",
                "derivado_a":          derivado_a if derivado_a else "-",
                "rnd_retiro":          round(rnd_retiro, 2) if rnd_retiro is not None else "-",
                "retiro_si_no":        retiro_si_no if retiro_si_no else "-",
                "triage_estado":       triage_estado,
                "triage_cola":         triage_cola,
                "od_estado":           od_estado,
                "od_cola":             od_cola,
                "od_contador_acepta":  od_contador_acepta,
                "cir_estado":          cir_estado,
                "cir_cola":            cir_cola,
                "cir_contador_pac":    cir_contador_pac,
                "cnt_llegadas":        cnt_llegadas,
                "cnt_retirados":       cnt_retirados,
                "pct_retirados":       pct_ret,
                "cnt_acepta_od":       cnt_acepta_od,
                "acum_espera_od":      round(acum_espera_odontologo, 2),
                "prom_espera_od":      prom_esp_od,
                "acum_libre_cir":      round(acum_libre_cirujano, 2),
                "acum_atiende_cir":    round(acum_atiende_cirujano, 2),
                "acum_esteril_cir":    round(acum_esteriliza_cirujano, 2),
                "acum_trabaja_cir":    round(acum_trabaja, 2),
                "pct_atiende_cir":     pct_at,
                "pct_esteril_cir":     pct_es,
                "pct_ocup_cir":        pct_oc,
                "pacientes":  {k: dict(v) for k, v in pacientes.items()},
                "pac_evento": pac_id,
                "es_ultima":  False,
            }

        # ── Fila 0 ────────────────────────────────────────────────────────
        f0 = snapshot("inicializacion", rnd_ll=rnd_ll0, t_ll=t_ll0)
        f0["iteracion"] = 0
        _maybe_save(f0)

        # ── Loop principal ─────────────────────────────────────────────────
        while True:
            evento, t_evento = prox_evento()
            if t_evento == INF or t_evento > self.tiempo_max or iteracion >= self.max_iter:
                break

            dt = t_evento - clock
            if   cir_estado == self.ATENDIENDO:    acum_atiende_cirujano    += dt
            elif cir_estado == self.ESTERILIZANDO: acum_esteriliza_cirujano += dt
            else:                                   acum_libre_cirujano      += dt

            clock = t_evento

            # ── LLEGADA ───────────────────────────────────────────────────
            if evento == "llegada_paciente":
                cnt_llegadas += 1
                pid = nuevo_id()
                rnd_ll2, t_ll2 = self._exp_neg(self.media_llegada)
                prox_llegada = clock + t_ll2

                t_triage_llegada = None
                if triage_estado == self.LIBRE and triage_cola == 0:
                    triage_estado    = self.ATENDIENDO
                    prox_fin_triage  = clock + self.tiempo_triage
                    t_triage_llegada = self.tiempo_triage
                    pacientes[pid]   = {"id": pid, "estado": "T",
                                        "inicio_espera_cola": None,
                                        "fin_espera": None, "timer_activo": False}
                else:
                    triage_cola    += 1
                    pacientes[pid]  = {"id": pid, "estado": "CT",
                                       "inicio_espera_cola": None,
                                       "fin_espera": None, "timer_activo": False}
                    cola_triage.append({"id": pid})

                _maybe_save(snapshot("llegada_paciente_P" + str(pid),
                                           rnd_ll=rnd_ll2, t_ll=t_ll2,
                                           t_triage=t_triage_llegada,
                                           pac_id=pid))

            # ── FIN TRIAGE ────────────────────────────────────────────────
            elif evento == "fin_triage":
                prox_fin_triage = INF
                pid_t = next((p for p, d in pacientes.items()
                              if d["estado"] == "T"), None)

                rnd_deriv = random.random()
                destino   = "Odontologo" if rnd_deriv < self.prob_odontologo else "Cirujano"

                rnd_od_v = t_od_v = None
                rnd_cir_v = t_cir_v = None
                t_pac_od = t_pac_cir = None

                if pid_t is not None:
                    pacientes[pid_t]["derivado_a"] = destino

                if destino == "Odontologo":
                    if od_estado == self.LIBRE:
                        od_estado          = self.ATENDIENDO
                        od_contador_acepta += 1
                        cnt_acepta_od      += 1
                        acum_espera_odontologo += 0.0
                        rnd_od_v, t_od_v    = self._exp_neg(self.media_odontologo)
                        prox_fin_odontologo = clock + t_od_v
                        if pid_t is not None:
                            pacientes[pid_t]["estado"] = "O"
                    else:
                        od_cola  += 1
                        fin_esp   = clock + self.tiempo_paciencia
                        t_pac_od  = self.tiempo_paciencia
                        if pid_t is not None:
                            pacientes[pid_t].update({"estado": "CO",
                                                     "inicio_espera_cola": clock,
                                                     "fin_espera": fin_esp,
                                                     "timer_activo": True})
                            cola_od.append({"id": pid_t, "fin_espera": fin_esp,
                                            "timer_activo": True,
                                            "inicio_espera": clock})
                        _recalc_fin_esper_od()
                else:
                    if cir_estado == self.LIBRE:
                        cir_estado          = self.ATENDIENDO
                        rnd_cir_v, t_cir_v  = self._uniforme(self.uniforme_a, self.uniforme_b)
                        prox_fin_cirujano    = clock + t_cir_v
                        if pid_t is not None:
                            pacientes[pid_t]["estado"] = "C"
                    else:
                        cir_cola  += 1
                        fin_esp    = clock + self.tiempo_paciencia
                        t_pac_cir  = self.tiempo_paciencia
                        if pid_t is not None:
                            pacientes[pid_t].update({"estado": "CC",
                                                     "inicio_espera_cola": clock,
                                                     "fin_espera": fin_esp,
                                                     "timer_activo": True})
                            cola_cir.append({"id": pid_t, "fin_espera": fin_esp,
                                             "timer_activo": True,
                                             "inicio_espera": clock})
                        _recalc_fin_esper_cir()

                if cola_triage:
                    sig = cola_triage.popleft()
                    triage_cola -= 1
                    pacientes[sig["id"]]["estado"] = "T"
                    prox_fin_triage = clock + self.tiempo_triage
                    triage_estado   = self.ATENDIENDO
                else:
                    triage_estado = self.LIBRE

                t_tr_snap = self.tiempo_triage if prox_fin_triage < INF else None
                _maybe_save(snapshot("fin_triage",
                                           t_triage=t_tr_snap,
                                           rnd_deriv=rnd_deriv, derivado_a=destino,
                                           rnd_od=rnd_od_v,  t_od=t_od_v,
                                           rnd_cir=rnd_cir_v, t_cir=t_cir_v,
                                           t_paciencia_od=t_pac_od,
                                           t_paciencia_cir=t_pac_cir,
                                           pac_id=pid_t))

            # ── FIN ESPERA COLA OD ────────────────────────────────────────
            elif evento == "fin_espera_en_cola_odontologo":
                prox_fin_esper_od = INF
                pac_imp = next((p for p in cola_od
                                if p.get("timer_activo")
                                and abs(p["fin_espera"] - clock) < 1e-4), None)
                rnd_ret   = random.random()
                se_retira = rnd_ret < self.prob_retiro
                pid_imp   = pac_imp["id"] if pac_imp else None

                if se_retira:
                    cnt_retirados += 1
                    if pid_imp:
                        pacientes[pid_imp]["estado"] = "Retirado"
                    if pac_imp in cola_od:
                        cola_od.remove(pac_imp)
                    od_cola = max(0, od_cola - 1)
                else:
                    if pac_imp:
                        pac_imp["timer_activo"] = False
                        if pid_imp:
                            pacientes[pid_imp]["timer_activo"] = False
                _recalc_fin_esper_od()

                _maybe_save(snapshot("fin_espera_en_cola_odontologo",
                                           rnd_retiro=rnd_ret,
                                           retiro_si_no="SI" if se_retira else "NO",
                                           pac_id=pid_imp))

            # ── FIN ESPERA COLA CIR ───────────────────────────────────────
            elif evento == "fin_espera_en_cola_cirujano":
                prox_fin_esper_cir = INF
                pac_imp = next((p for p in cola_cir
                                if p.get("timer_activo")
                                and abs(p["fin_espera"] - clock) < 1e-4), None)
                rnd_ret   = random.random()
                se_retira = rnd_ret < self.prob_retiro
                pid_imp   = pac_imp["id"] if pac_imp else None

                if se_retira:
                    cnt_retirados += 1
                    if pid_imp:
                        pacientes[pid_imp]["estado"] = "Retirado"
                    if pac_imp in cola_cir:
                        cola_cir.remove(pac_imp)
                    cir_cola = max(0, cir_cola - 1)
                else:
                    if pac_imp:
                        pac_imp["timer_activo"] = False
                        if pid_imp:
                            pacientes[pid_imp]["timer_activo"] = False
                _recalc_fin_esper_cir()

                _maybe_save(snapshot("fin_espera_en_cola_cirujano",
                                           rnd_retiro=rnd_ret,
                                           retiro_si_no="SI" if se_retira else "NO",
                                           pac_id=pid_imp))

            # ── FIN ODONTOLOGO ────────────────────────────────────────────
            elif evento == "fin_odontologo":
                prox_fin_odontologo = INF
                pid_od = next((p for p, d in pacientes.items()
                               if d["estado"] == "O"), None)
                if pid_od:
                    pacientes[pid_od]["estado"] = "Atendido"

                rnd_od_v = t_od_v = None
                if cola_od:
                    sig     = cola_od.popleft()
                    od_cola -= 1
                    pid_sig  = sig["id"]
                    espera   = clock - sig["inicio_espera"]
                    acum_espera_odontologo += espera
                    cnt_acepta_od      += 1
                    od_contador_acepta += 1
                    pacientes[pid_sig]["estado"]       = "O"
                    pacientes[pid_sig]["timer_activo"] = False
                    rnd_od_v, t_od_v    = self._exp_neg(self.media_odontologo)
                    prox_fin_odontologo = clock + t_od_v
                    od_estado = self.ATENDIENDO
                    _recalc_fin_esper_od()
                else:
                    od_estado = self.LIBRE

                _maybe_save(snapshot("fin_odontologo",
                                           rnd_od=rnd_od_v, t_od=t_od_v,
                                           pac_id=pid_od))

            # ── FIN CIRUJANO ──────────────────────────────────────────────
            elif evento == "fin_cirujano":
                prox_fin_cirujano  = INF
                cir_atendidos     += 1
                cir_contador_pac  += 1

                pid_cir = next((p for p, d in pacientes.items()
                                if d["estado"] == "C"), None)
                if pid_cir:
                    pacientes[pid_cir]["estado"] = "Atendido"

                esteriliza = (cir_atendidos % self.pac_para_esterilizar == 0)
                rnd_cir_v = t_cir_v = None

                if esteriliza:
                    cir_estado              = self.ESTERILIZANDO
                    prox_fin_esterilizacion = clock + self.tiempo_esterilizacion
                else:
                    if cola_cir:
                        sig     = cola_cir.popleft()
                        cir_cola -= 1
                        pid_sig  = sig["id"]
                        pacientes[pid_sig]["estado"]       = "C"
                        pacientes[pid_sig]["timer_activo"] = False
                        _recalc_fin_esper_cir()
                        rnd_cir_v, t_cir_v  = self._uniforme(self.uniforme_a, self.uniforme_b)
                        prox_fin_cirujano    = clock + t_cir_v
                        cir_estado           = self.ATENDIENDO
                    else:
                        cir_estado = self.LIBRE

                _maybe_save(snapshot("fin_cirujano",
                                           rnd_cir=rnd_cir_v, t_cir=t_cir_v,
                                           pac_id=pid_cir))

            # ── FIN ESTERILIZACION ─────────────────────────────────────────
            elif evento == "fin_esterilizacion":
                prox_fin_esterilizacion = INF
                rnd_cir_v = t_cir_v = None

                if cola_cir:
                    sig     = cola_cir.popleft()
                    cir_cola -= 1
                    pid_sig  = sig["id"]
                    pacientes[pid_sig]["estado"]       = "C"
                    pacientes[pid_sig]["timer_activo"] = False
                    _recalc_fin_esper_cir()
                    rnd_cir_v, t_cir_v  = self._uniforme(self.uniforme_a, self.uniforme_b)
                    prox_fin_cirujano    = clock + t_cir_v
                    cir_estado           = self.ATENDIENDO
                else:
                    cir_estado = self.LIBRE

                _maybe_save(snapshot("fin_esterilizacion",
                                           rnd_cir=rnd_cir_v, t_cir=t_cir_v))

            # Purgar pacientes terminados cada 500 iters (ahorro de memoria)
            if iteracion % 500 == 0:
                to_del = [pid for pid, v in pacientes.items()
                          if v["estado"] in ("Atendido", "Retirado")]
                for pid in to_del:
                    del pacientes[pid]

        # ── Ultima fila ────────────────────────────────────────────────────
        ultimo_evento_nombre = evento if t_evento != INF else "sin_eventos"
        self.ultima_fila = snapshot(ultimo_evento_nombre, _incrementar=False)
        self.ultima_fila["es_ultima"] = True

        # ── Estadisticas finales ───────────────────────────────────────────
        acum_trabaja = (acum_libre_cirujano
                        + acum_atiende_cirujano
                        + acum_esteriliza_cirujano)

        # Redondear acumuladores antes de calcular % finales (coherencia)
        _libre_f   = round(acum_libre_cirujano,      2)
        _atiende_f = round(acum_atiende_cirujano,    2)
        _esteril_f = round(acum_esteriliza_cirujano, 2)
        acum_trabaja = round(_libre_f + _atiende_f + _esteril_f, 2)

        pct_at = round(_atiende_f / acum_trabaja * 100, 2) if acum_trabaja else 0
        pct_es = round(_esteril_f / acum_trabaja * 100, 2) if acum_trabaja else 0
        pct_oc = round(pct_at + pct_es, 2)

        self.estadisticas = {
            "total_llegadas":      cnt_llegadas,
            "total_retirados":     cnt_retirados,
            "pct_retirados":       round(cnt_retirados / cnt_llegadas * 100, 2) if cnt_llegadas else 0,
            "cnt_acepta_od":       cnt_acepta_od,
            "acum_espera_od":      round(acum_espera_odontologo, 2),
            "prom_espera_od":      round(round(acum_espera_odontologo, 2) / cnt_acepta_od, 2) if cnt_acepta_od else 0,
            "acum_libre_cir":      _libre_f,
            "acum_atiende_cir":    _atiende_f,
            "acum_esteril_cir":    _esteril_f,
            "acum_trabaja_cir":    acum_trabaja,
            "pct_atiende_cir":     pct_at,
            "pct_esteril_cir":     pct_es,
            "pct_ocup_cir":        pct_oc,
            "tiempo_simulado":     round(clock, 2),
            "iteraciones_totales": iteracion,
        }
        return self.filas, self.ultima_fila, self.estadisticas

    # ── Filtrado: i filas desde hora j ────────────────────────────────────
    def get_filas_filtradas(self):
        # La fila 0 (inicializacion) se incluye siempre si cae en el rango
        # pero NO cuenta contra el limite i; las iteraciones 1..N si cuentan.
        j_hora = self.j_hora
        i      = self.cant_mostrar
        fila_0    = [f for f in self.filas if f["iteracion"] == 0 and f["hora"] >= j_hora]
        resto     = [f for f in self.filas if f["iteracion"] != 0 and f["hora"] >= j_hora]
        return fila_0 + resto[:i]

    # ── DataFrame ────────────────────────────────────────────────────────
    def to_dataframe(self, filas=None):
        if filas is None:
            filas = self.filas
        if not filas:
            return pd.DataFrame()

        rows = []
        for f in filas:
            pacs = f.get("pacientes", {})

            def _pacs_en(codigo):
                partes = []
                for pid, v in pacs.items():
                    if v["estado"] == codigo:
                        iec = v.get("inicio_espera_cola")
                        if iec is not None:
                            partes.append("P" + str(pid) + "(" + str(round(iec, 2)) + ")")
                        else:
                            partes.append("P" + str(pid))
                return "; ".join(partes) if partes else "-"

            rows.append({
                "i":                          f["iteracion"],
                "Dia":                        f["dia"],
                "Hora":                       f["hora"],
                "Clock (min)":                f["clock"],
                "Evento":                     f["evento"],
                "RND Llegada":                f["rnd_llegada"],
                "T Entre Llegadas":           f["t_entre_llegadas"],
                "Prox. Llegada":              f["prox_llegada"],
                "T Triage":                   f["t_triage"],
                "fin_triage":                 f["prox_fin_triage"],
                "T Espera OD":                f["t_paciencia_od"],
                "fin_espera_od":              f["prox_fin_esper_od"],
                "T Espera Cir":               f["t_paciencia_cir"],
                "fin_espera_cir":             f["prox_fin_esper_cir"],
                "RND Odontologo":             f["rnd_odontologo"],
                "T Atencion Od.":             f["t_atencion_od"],
                "fin_odontologo":             f["prox_fin_odontologo"],
                "RND Cirujano":               f["rnd_cirujano"],
                "T Atencion Cir.":            f["t_atencion_cir"],
                "fin_cirujano":               f["prox_fin_cirujano"],
                "T Esterilizacion":           f["t_esterilizacion"],
                "fin_esterilizacion":         f["prox_fin_esteril"],
                "RND Derivacion":             f["rnd_deriv"],
                "Derivado A":                 f["derivado_a"],
                "RND Retiro":                 f["rnd_retiro"],
                "Se Retira":                  f["retiro_si_no"],
                "TRIAGE Estado":              f["triage_estado"],
                "TRIAGE Cola":                f["triage_cola"],
                "OD Estado":                  f["od_estado"],
                "OD Cola":                    f["od_cola"],
                "OD Acepta (ctd)":            f["od_contador_acepta"],
                "CIR Estado":                 f["cir_estado"],
                "CIR Cola":                   f["cir_cola"],
                "CIR Pac. Atendidos":         f["cir_contador_pac"],
                "Llegadas":                   f["cnt_llegadas"],
                "Retirados":                  f["cnt_retirados"],
                "% Retirados":                f["pct_retirados"],
                "Acepta OD":                  f["cnt_acepta_od"],
                "Acum. Esp. OD (min)":        f["acum_espera_od"],
                "Prom. Esp. OD (min)":        f["prom_espera_od"],
                "Acum. Libre CIR (min)":      f["acum_libre_cir"],
                "Acum. Atiende CIR (min)":    f["acum_atiende_cir"],
                "Acum. Esteril. CIR (min)":   f["acum_esteril_cir"],
                "Acum. Trabaja CIR (min)":    f["acum_trabaja_cir"],
                "% Atencion CIR":             f["pct_atiende_cir"],
                "% Esteriliz. CIR":           f["pct_esteril_cir"],
                "% Ocupacion CIR":            f["pct_ocup_cir"],
                "CT (Cola Triage)":           _pacs_en("CT"),
                "T  (En Triage)":             _pacs_en("T"),
                "CO (Cola Odontologo)":       _pacs_en("CO"),
                "O  (En Odontologo)":         _pacs_en("O"),
                "CC (Cola Cirujano)":         _pacs_en("CC"),
                "C  (En Cirujano)":           _pacs_en("C"),
            })
        return pd.DataFrame(rows)


if __name__ == "__main__":
    import tkinter as tk
    try:
        from UI import AppSimulacion
        root = tk.Tk()
        AppSimulacion(root)
        root.mainloop()
    except ImportError:
        print("Ejecuta UI.py directamente.")
