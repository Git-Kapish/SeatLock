FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=3s --retries=3 \
    CMD wget -q -O - http://127.0.0.1:8000/health/live || exit 1

CMD ["nginx", "-g", "daemon off;"]
