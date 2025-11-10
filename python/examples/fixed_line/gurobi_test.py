import gurobipy as gp
from gurobipy import GRB
import os
from pathlib import Path

# === 1️⃣ Spécifie ici le chemin ABSOLU de ton fichier LP ===
# ⚠️ Utilise r"..." ou remplace les '\' par des '/'
lp_path = r"C:\gurobi_tests\model_debug.lp"
model = gp.read(lp_path)
model.optimize()

# === 4️⃣ Lancement de l'optimisation ===
model.optimize()

# === 5️⃣ Vérification du statut ===
if model.status == GRB.INFEASIBLE:
    print("\n❌ Le modèle est infaisable.")
    print("🔎 Calcul de l'IIS (Irreducible Inconsistent Subsystem)...")

    # === 6️⃣ Calcul de l'IIS ===
    model.computeIIS()

    # === 7️⃣ Sauvegarde de l'IIS dans un fichier .ilp ===
    iis_path = os.path.join(os.path.dirname(lp_path), "model_debug.ilp")
    model.write(iis_path)

    print(f"✅ IIS sauvegardé ici : {iis_path}")
    print("👉 Ouvre ce fichier avec un éditeur de texte pour voir les contraintes contradictoires.")

elif model.status == GRB.OPTIMAL:
    print("\n✅ Modèle réalisable et solution optimale trouvée.")
    print(f"Valeur optimale = {model.ObjVal:.4f}")
else:
    print(f"\nℹ️ Statut du modèle : {model.status}")
