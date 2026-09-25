from setting_circuit import *
import time

tick = 0

while len(vehicules) > 0:
    print(f"--- Tick {tick} ---")

    vehicules_encore_actifs = []

    for v in vehicules:
        resultat = v.avancer(circuit)

        prefixe = "[URGENCE] " if v.est_urgent else "          "
        print(f"{prefixe}{v.depart} -> {v.arrivee} | avancement={round(v.avancement, 2)} | {resultat}")

        if resultat != "arrive":
            vehicules_encore_actifs.append(v)

    vehicules = vehicules_encore_actifs

    if tick % 15 == 0:
        for noeud in ['A', 'B', 'D']:
            phase_actuelle = circuit.noeuds[noeud]["phase_active"]
            nombre_de_phases = len(circuit.noeuds[noeud]["phases"])
            nouvelle_phase = (phase_actuelle + 1) % nombre_de_phases
            circuit.changer_phase(noeud, nouvelle_phase)

    tick = tick + 1
    time.sleep(0.3)