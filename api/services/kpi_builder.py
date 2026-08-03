"""
Logique de calcul / recalcul des ratios techniques (RC, RSP, RF) par compagnie.
Extraite de routes/comparative.py pour être réutilisée par routes/qualite.py.
"""

from api.utils.formatters import round1, PRIMES_UNIT_DIVISOR


def _raw_ratio(v):
    """Valeur brute valide : 2 % ≤ v ≤ 1 000 % (hors aberrations extraction)."""
    return v if (v is not None and 2 <= v <= 1_000) else None


def build_company_row(kpis, primes_prev_year, total_ftusa, code):
    """
    Construit le dict de KPIs d'affichage pour une compagnie/année.

    Retourne un dict avec les clés attendues par le frontend, plus
    des champs de diagnostic (prefixés `_`) pour le rapport qualité.
    """
    # ── Primes émises ──────────────────────────────────────────────────────────
    primes_nv  = kpis.get("Primes émises Non-Vie par assurance")
    primes_vie = kpis.get("Primes émises Vie par assurance")
    primes_raw = kpis.get("Primes émises par assurance")

    if (primes_vie is not None and primes_vie > 1_000 and
            primes_nv is not None and primes_nv > 1_000):
        primes_raw = primes_vie + primes_nv

    primes_raw_is_bad = primes_raw is None or primes_raw < 1_000
    if primes_raw_is_bad:
        primes_raw = kpis.get("Primes acquises") or kpis.get("Total Primes émises")

    # ── PDM ────────────────────────────────────────────────────────────────────
    if primes_raw and not primes_raw_is_bad and total_ftusa and total_ftusa > 0:
        pdm = primes_raw / total_ftusa * 100
    else:
        pdm = None if primes_raw_is_bad else kpis.get("Part de marché (%)")

    # ── Ratios extraits du PDF ──────────────────────────────────────────────────
    rc  = _raw_ratio(kpis.get("Ratio combiné (%)"))
    rsp = _raw_ratio(kpis.get("Ratio de sinistralité (%)"))
    rf  = _raw_ratio(kpis.get("Ratio de frais de gestion (%)"))

    # Invalider RC quand RC ≈ RF (même ligne lue deux fois)
    if rc is not None and rf is not None and abs(rc - rf) < 0.5:
        rc = None

    # ── Charges brutes ─────────────────────────────────────────────────────────
    primes_brutes_raw = kpis.get("Primes émises par assurance")
    primes_for_rc_rf = (
        primes_raw if (primes_brutes_raw is None or primes_brutes_raw < 1_000)
        else primes_brutes_raw
    )

    primes_acquises = kpis.get("Primes acquises")
    rsp_extracted_unreliable = False
    if (primes_acquises and primes_acquises > 1_000
            and primes_for_rc_rf and primes_for_rc_rf > 0
            and primes_acquises > primes_for_rc_rf * 2):
        primes_acquises = None
        rsp_extracted_unreliable = True

    denom_rsp = (
        primes_acquises if (primes_acquises and primes_acquises > 1_000)
        else primes_for_rc_rf
    )

    nv_only = (
        primes_nv is not None and primes_nv > 1_000 and primes_for_rc_rf is not None and
        abs(primes_nv - primes_for_rc_rf) / max(primes_nv, primes_for_rc_rf) < 0.01
    ) if primes_for_rc_rf else False

    charge_sin      = kpis.get("Charge de sinistres")
    charge_sin_nv   = kpis.get("Charge de sinistres Non-Vie")
    charge_sin_vie  = kpis.get("Charge de sinistres Vie")
    charge_prest    = kpis.get("Charges de prestations")
    charge_prest_nv = kpis.get("Charges de prestations Non-Vie")
    charge_prest_vie= kpis.get("Charges de prestations Vie")
    charge_frais    = kpis.get("Charges d'acquisition et de gestion nettes")
    charge_frais_vie= kpis.get("Charges d'acquisition et de gestion nettes Vie")

    _vie_ch = abs(charge_prest_vie or 0) + abs(charge_frais_vie or 0)
    _tot_ch_est = abs(charge_prest or 0) + abs(charge_frais or 0) if charge_prest or charge_frais else 0
    _vie_weight = _vie_ch / _tot_ch_est if _tot_ch_est else 0
    _vie_primes_missing = primes_vie is None or primes_vie < 1_000
    _rc_vie_nv_mismatch = _vie_primes_missing and _vie_weight > 0.10

    if primes_for_rc_rf and primes_for_rc_rf > 0:
        if rsp is None and denom_rsp and denom_rsp > 0:
            if nv_only:
                if charge_sin_nv is not None:
                    candidate = abs(charge_sin_nv) / denom_rsp * 100
                    rsp = candidate if candidate >= 2 else None
                if rsp is None and charge_prest_nv is not None:
                    rsp = abs(charge_prest_nv) / denom_rsp * 100
            else:
                sin_total = None
                if charge_sin_vie is not None and charge_sin_nv is not None:
                    sin_total = abs(charge_sin_vie) + abs(charge_sin_nv)
                elif charge_sin is not None:
                    sin_total = abs(charge_sin)
                if sin_total is not None:
                    rsp = sin_total / denom_rsp * 100
                elif charge_prest is not None:
                    rsp = abs(charge_prest) / denom_rsp * 100

        if rf is None and charge_frais is not None:
            rf = abs(charge_frais) / primes_for_rc_rf * 100

        if rc is None and rsp_extracted_unreliable and charge_frais is not None and not _rc_vie_nv_mismatch:
            prest_total = _prest_total(charge_prest_vie, charge_prest_nv, charge_prest,
                                        charge_sin_vie, charge_sin_nv, charge_sin)
            if prest_total is not None:
                rc = (prest_total + abs(charge_frais)) / primes_for_rc_rf * 100

    # Fallback algébrique partiel
    if rsp is None and rc is not None and rf is not None:
        rsp = rc - rf
    if rf is None and rc is not None and rsp is not None:
        rf = rc - rsp

    # Fallback 2 depuis les charges
    if primes_for_rc_rf and primes_for_rc_rf > 0:
        if rc is None and not _rc_vie_nv_mismatch:
            charge_frais = kpis.get("Charges d'acquisition et de gestion nettes")
            if charge_frais is not None:
                prest_total = _prest_total(charge_prest_vie, charge_prest_nv, charge_prest,
                                            charge_sin_vie, charge_sin_nv, charge_sin)
                if prest_total is not None:
                    rc = (prest_total + abs(charge_frais)) / primes_for_rc_rf * 100

        if rc is None and _rc_vie_nv_mismatch and primes_nv is not None and primes_nv > 1_000:
            _cp_nv = kpis.get("Charges de prestations Non-Vie")
            _ca_nv = kpis.get("Charges d'acquisition et de gestion nettes Non-Vie")
            if _cp_nv is not None and _ca_nv is not None:
                rc = (abs(_cp_nv) + abs(_ca_nv)) / primes_nv * 100

    if rsp is not None and rsp < 2: rsp = None
    if rf is not None  and rf < 2:  rf  = None

    # ── Résultat technique ─────────────────────────────────────────────────────
    rt_raw = kpis.get("Résultat technique (TND)")
    rt_mdt = round1(rt_raw / PRIMES_UNIT_DIVISOR) if rt_raw is not None else None

    # ── Croissance primes YoY ──────────────────────────────────────────────────
    p_prev = primes_prev_year.get(code)
    if primes_raw and p_prev and p_prev > 0:
        croissance = round1((primes_raw - p_prev) / p_prev * 100)
    else:
        croissance = None

    def _ratio_guard(v):
        if v is None or v < 2 or v > 1_000:
            return None
        return round1(v)

    return {
        "pdm":               round1(pdm),
        "primes":            round1(primes_raw / PRIMES_UNIT_DIVISOR) if primes_raw else None,
        "ratio_combine":     _ratio_guard(rc),
        "ratio_sp":          _ratio_guard(rsp),
        "ratio_frais":       _ratio_guard(rf),
        "roe":               round1(kpis.get("ROE (%)")),
        "roa":               round1(kpis.get("ROA (%)")),
        "resultat_technique": rt_mdt,
        "croissance_primes":  croissance,
        # champs de diagnostic (non exposés au frontend)
        "_rc_vie_nv_mismatch":     _rc_vie_nv_mismatch,
        "_rsp_unreliable":         rsp_extracted_unreliable,
        "_primes_bad":             primes_raw_is_bad,
    }


def _prest_total(charge_prest_vie, charge_prest_nv, charge_prest,
                  charge_sin_vie, charge_sin_nv, charge_sin):
    if charge_prest_vie is not None and charge_prest_nv is not None:
        return abs(charge_prest_vie) + abs(charge_prest_nv)
    if charge_prest is not None:
        return abs(charge_prest)
    if charge_sin_vie is not None and charge_sin_nv is not None:
        return abs(charge_sin_vie) + abs(charge_sin_nv)
    if charge_sin is not None:
        return abs(charge_sin)
    return None
