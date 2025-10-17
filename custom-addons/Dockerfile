# Official Odoo 17 base image
FROM odoo:17.0

# (Optional) agar kuch OS libs chahiye hon to yahan install karein
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
#     libpq-dev git && rm -rf /var/lib/apt/lists/*

# Python dependencies (optional)
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt || true

# AAP KA PURE ADDONS REPO -> /mnt/extra-addons
# (Is repo me root par hi modules hain, isliye "." copy kar rahe hain)
COPY . /mnt/extra-addons
RUN chown -R odoo:odoo /mnt/extra-addons

# Odoo config copy (env-driven)
COPY odoo.conf /etc/odoo/odoo.conf
RUN chown -R odoo:odoo /etc/odoo

# Defaults (Coolify env se override ho jayenge)
ENV ADDONS_PATH="/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons"
ENV XMLRPC_PORT=8069
ENV LONGPOLLING_PORT=8072

EXPOSE 8069 8072

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD wget -q -O- http://127.0.0.1:${XMLRPC_PORT} >/dev/null 2>&1 || exit 1
