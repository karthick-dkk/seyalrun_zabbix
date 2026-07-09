FROM nginxinc/nginx-unprivileged:1.27-alpine

# Template (not a static conf): the base image's entrypoint runs envsubst over
# /etc/nginx/templates/*.template at boot, substituting ${FRAME_ANCESTORS} and
# leaving nginx's own $-vars intact, then writes /etc/nginx/conf.d/default.conf.
COPY services/edge-proxy/templates/default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080 8443
