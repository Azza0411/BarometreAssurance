# Image du chatbot IA (port 5001) — FS Market Intelligence
FROM python:3.12-slim

WORKDIR /app

# Prophet et XGBoost fournissent des wheels precompiles pour Linux (pas de
# compilation locale necessaire) : pas besoin de build-essential ici, ce
# qui evite ~336 Mo de paquets systeme (gcc, binutils...) a telecharger.
COPY chatbot_portable/requirements.txt .
# --default-timeout/--retries : les roues volumineuses (xgboost, nvidia-nccl)
# font parfois expirer le timeout socket par defaut de pip (15s) sur une
# connexion lente, sans que le paquet soit realmente en cause.
RUN pip install --no-cache-dir --default-timeout=100 --retries 5 -r requirements.txt gunicorn python-dotenv

COPY chatbot_portable/ .

# MarketInsurance.db et .env sont montes en volume (docker-compose), pas
# embarques dans l'image : la base evolue independamment des deploiements.
EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "300", "app:app"]
