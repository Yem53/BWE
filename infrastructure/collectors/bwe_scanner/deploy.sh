#!/bin/bash
# Ship the bwe_scanner flat modules + config + systemd unit to EC2 Tokyo.
# Run from the Mac. Does NOT enable the service (that's a separate manual step
# after the Telegram chat id is set).
set -euo pipefail
EC2=ubuntu@13.159.69.106
KEY=~/.ssh/bwe-tokyo.pem
SRC=/Volumes/T9/BWE/infrastructure/collectors/bwe_scanner
DST=/home/ubuntu/bwe-scanner

ssh -i "$KEY" "$EC2" "mkdir -p $DST/data $DST/logs"
# flat modules + config (NOT tests, NOT ._* AppleDouble files)
scp -i "$KEY" \
  "$SRC/scanner.py" "$SRC/detectors.py" "$SRC/ws_feed.py" "$SRC/enrich.py" \
  "$SRC/store.py" "$SRC/notify.py" "$SRC/config.json" "$SRC/symbol_cg_map.json" \
  "$EC2:$DST/"
scp -i "$KEY" "$SRC/bwe-scanner.service" "$EC2:/tmp/bwe-scanner.service"
ssh -i "$KEY" "$EC2" "sudo mv /tmp/bwe-scanner.service /etc/systemd/system/ && sudo systemctl daemon-reload"
echo "deployed to $DST (service installed, NOT enabled)"
