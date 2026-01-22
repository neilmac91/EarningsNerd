#!/bin/bash
# performance-comparison.sh

echo "=== Performance Baseline Capture ==="
echo "Timestamp: $(date)" > performance-baseline.txt

echo -e "\n[Frontend Build]" >> performance-baseline.txt
(time npm run build) 2>&1 | grep real >> performance-baseline.txt

echo -e "\n[Frontend Tests]" >> performance-baseline.txt
(time npm run test) 2>&1 | grep real >> performance-baseline.txt

echo -e "\n[Backend Tests]" >> performance-baseline.txt
(cd backend && time pytest) 2>&1 | grep real >> performance-baseline.txt

# Note: We can't easily run 'wrk' against localhost in this environment without ensuring the server is running.
# For this environment, we will skip the live API load test in the script and rely on the build/test metrics
# unless the server is explicitly started.
echo -e "\n[API Performance]" >> performance-baseline.txt
echo "Skipping live API load test (server not running)" >> performance-baseline.txt

echo "Baseline captured in performance-baseline.txt"
cat performance-baseline.txt
