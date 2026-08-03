# Image du frontend React/Vite, servie par Nginx (port 80) — FS Market Intelligence
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
# --legacy-peer-deps : react-simple-maps@3.0.0 déclare un peer React <=18,
# mais le projet est en React 19 (fonctionne en pratique, ce paquet n'a
# juste pas encore mis à jour sa déclaration de peerDependencies). `npm
# install` local ignore ce conflit ; `npm ci` (utilisé ici, plus strict)
# le bloque sans ce flag.
RUN npm ci --legacy-peer-deps

COPY . .

# VITE_API_URL vide = chemin relatif "/api/..." (deja prefixe cote Flask),
# VITE_CHATBOT_URL="/chatbot" = proxifie par Nginx vers le service chatbot
# (voir nginx.conf). Surchargeables au build (--build-arg) si besoin.
ARG VITE_API_URL=
ARG VITE_CHATBOT_URL=/chatbot
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_CHATBOT_URL=$VITE_CHATBOT_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
