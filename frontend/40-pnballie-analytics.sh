#!/bin/sh
# The root filesystem remains read-only; nginx includes only generated /tmp files.
set -eu
runtime_dir=${PNBALLIE_RUNTIME_DIR:-/tmp}
mkdir -p "$runtime_dir"
enabled=false
website=''
upstream=${ANALYTICS_UPSTREAM:-}
website_candidate=${ANALYTICS_WEBSITE_ID:-}
case "$upstream" in *[!a-zA-Z0-9.:-]*) upstream='' ;; esac
case "$website_candidate" in *[!a-fA-F0-9-]*) website_candidate='' ;; esac
case ${ANALYTICS_ENABLED:-false} in true|1)
  if printf '%s' "$website_candidate" | grep -Eq '^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$' &&
     printf '%s' "$upstream" | grep -Eq '^[a-zA-Z0-9][a-zA-Z0-9.-]*:[0-9]{1,5}$'; then
    enabled=true
    website=$ANALYTICS_WEBSITE_ID
  else
    echo 'PNBallie analytics disabled: invalid website ID or private upstream.' >&2
  fi
esac
printf '{"analytics":{"enabled":%s,"websiteId":"%s"}}\n' "$enabled" "$website" > "$runtime_dir/pnballie-config.json"

# Only explicitly trusted proxy CIDRs may supply CF-Connecting-IP. A preview
# through another proxy must never inherit a visitor-supplied forwarding header.
printf 'geo $realip_remote_addr $analytics_from_trusted_proxy {\n default 0;\n' > "$runtime_dir/pnballie-analytics-http.conf"
: > "$runtime_dir/pnballie-analytics-server.conf"
for cidr in $(printf '%s' "${ANALYTICS_TRUSTED_PROXY_CIDRS:-}" | tr ',' ' '); do
  if printf '%s\n' "$cidr" | awk -F'[./]' 'NF != 5 {exit 1} {for(i=1;i<=5;i++) if($i !~ /^[0-9]+$/) exit 1; for(i=1;i<=4;i++) if($i>255) exit 1; if($5<8 || $5>32) exit 1}'; then
    printf ' %s 1;\n' "$cidr" >> "$runtime_dir/pnballie-analytics-http.conf"
    printf 'set_real_ip_from %s;\n' "$cidr" >> "$runtime_dir/pnballie-analytics-server.conf"
  else
    echo 'PNBallie analytics ignored an invalid trusted proxy CIDR.' >&2
  fi
done
cat >> "$runtime_dir/pnballie-analytics-http.conf" <<'EOF'
}
map $analytics_from_trusted_proxy $analytics_client_ip {
 default "";
 1 $remote_addr;
}
EOF
cat >> "$runtime_dir/pnballie-analytics-server.conf" <<'EOF'
real_ip_header CF-Connecting-IP;
real_ip_recursive off;
EOF
cat > "$runtime_dir/pnballie-analytics-proxy.conf" <<'EOF'
proxy_pass_request_headers off;
proxy_set_header Host $host;
proxy_set_header Content-Type $http_content_type;
proxy_set_header User-Agent $http_user_agent;
proxy_set_header X-Umami-Cache $http_x_umami_cache;
proxy_set_header X-Umami-Website-Id $http_x_umami_website_id;
proxy_set_header X-Umami-Hostname $http_x_umami_hostname;
proxy_set_header Cookie "";
proxy_set_header Authorization "";
proxy_set_header Referer "";
proxy_set_header Forwarded "";
proxy_set_header X-Forwarded-For $analytics_client_ip;
proxy_set_header X-Real-IP $analytics_client_ip;
proxy_set_header X-Forwarded-Host "";
proxy_set_header X-Forwarded-Proto "";
proxy_set_header X-Original-Forwarded-For "";
proxy_set_header X-Client-IP "";
proxy_set_header True-Client-IP "";
proxy_set_header CF-Connecting-IP "";
proxy_set_header CF-IPCountry "";
proxy_hide_header Set-Cookie;
proxy_connect_timeout 2s;
proxy_read_timeout 5s;
proxy_send_timeout 5s;
access_log off;
EOF
if [ "$enabled" = true ]; then
  resolver=${ANALYTICS_DNS_RESOLVER:-$(awk '$1 == "nameserver" {print $2; exit}' /etc/resolv.conf)}
  case "$resolver" in *[!0-9.]*) resolver=127.0.0.11 ;; esac
  if ! printf '%s' "$resolver" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$'; then resolver=127.0.0.11; fi
  cat >> "$runtime_dir/pnballie-analytics-server.conf" <<EOF
resolver $resolver valid=30s ipv6=off;
location = /analytics/script.js {
 limit_except GET { deny all; }
 set \$analytics_backend "http://$upstream";
 proxy_pass \$analytics_backend/script.js;
 include "$runtime_dir/pnballie-analytics-proxy.conf";
 add_header Cache-Control "public, max-age=3600";
}
location = /analytics/api/send {
 limit_except POST { deny all; }
 client_max_body_size 16k;
 set \$analytics_backend "http://$upstream";
 proxy_pass \$analytics_backend/api/send;
 include "$runtime_dir/pnballie-analytics-proxy.conf";
 add_header Cache-Control "no-store";
}
EOF
fi
