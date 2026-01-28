#!/bin/bash
# Vercel Claimable Deployment Script
# Packages and deploys projects to Vercel with claimable URLs

set -e

DEPLOY_ENDPOINT="https://claude-skills-deploy.vercel.com/api/deploy"

# Detect framework from package.json
detect_framework() {
    local pkg_json="$1/package.json"

    if [[ ! -f "$pkg_json" ]]; then
        echo "null"
        return
    fi

    local deps=$(cat "$pkg_json" | grep -E '"(dependencies|devDependencies)"' -A 100 | head -100)

    # Order matters - check more specific frameworks first
    if echo "$deps" | grep -q '"next"'; then
        echo "nextjs"
    elif echo "$deps" | grep -q '"@remix-run/react"'; then
        echo "remix"
    elif echo "$deps" | grep -q '"gatsby"'; then
        echo "gatsby"
    elif echo "$deps" | grep -q '"astro"'; then
        echo "astro"
    elif echo "$deps" | grep -q '"@sveltejs/kit"'; then
        echo "sveltekit"
    elif echo "$deps" | grep -q '"svelte"'; then
        echo "svelte"
    elif echo "$deps" | grep -q '"nuxt"'; then
        echo "nuxt"
    elif echo "$deps" | grep -q '"vue"'; then
        echo "vue"
    elif echo "$deps" | grep -q '"@angular/core"'; then
        echo "angular"
    elif echo "$deps" | grep -q '"solid-js"'; then
        echo "solid"
    elif echo "$deps" | grep -q '"preact"'; then
        echo "preact"
    elif echo "$deps" | grep -q '"react"'; then
        echo "create-react-app"
    elif echo "$deps" | grep -q '"@nestjs/core"'; then
        echo "nestjs"
    elif echo "$deps" | grep -q '"express"'; then
        echo "express"
    elif echo "$deps" | grep -q '"fastify"'; then
        echo "fastify"
    elif echo "$deps" | grep -q '"hono"'; then
        echo "hono"
    elif echo "$deps" | grep -q '"koa"'; then
        echo "koa"
    else
        echo "other"
    fi
}

# Handle static HTML projects
handle_static_html() {
    local dir="$1"
    local html_files=$(find "$dir" -maxdepth 1 -name "*.html" | wc -l)

    if [[ $html_files -eq 1 ]]; then
        local html_file=$(find "$dir" -maxdepth 1 -name "*.html")
        local basename=$(basename "$html_file")
        if [[ "$basename" != "index.html" ]]; then
            echo "Renaming $basename to index.html for static deployment" >&2
            mv "$html_file" "$dir/index.html"
        fi
    fi
}

# Create tarball from directory
create_tarball() {
    local source_dir="$1"
    local tarball_path=$(mktemp /tmp/deploy-XXXXXX.tgz)

    tar -czf "$tarball_path" \
        --exclude='node_modules' \
        --exclude='.git' \
        --exclude='.next' \
        --exclude='dist' \
        --exclude='.vercel' \
        --exclude='*.log' \
        -C "$source_dir" .

    echo "$tarball_path"
}

# Main deployment function
deploy() {
    local input="${1:-.}"
    local tarball_path=""
    local framework=""
    local cleanup_tarball=false

    # Determine input type
    if [[ "$input" == *.tgz || "$input" == *.tar.gz ]]; then
        # Pre-packaged tarball
        if [[ ! -f "$input" ]]; then
            echo "Error: Tarball not found: $input" >&2
            exit 1
        fi
        tarball_path="$input"
        framework="other"
    else
        # Directory path
        if [[ ! -d "$input" ]]; then
            echo "Error: Directory not found: $input" >&2
            exit 1
        fi

        # Detect framework
        framework=$(detect_framework "$input")
        echo "Detected framework: $framework" >&2

        # Handle static HTML
        if [[ "$framework" == "null" ]]; then
            handle_static_html "$input"
        fi

        # Create tarball
        echo "Creating deployment package..." >&2
        tarball_path=$(create_tarball "$input")
        cleanup_tarball=true
    fi

    # Upload to deployment endpoint
    echo "Uploading to Vercel..." >&2

    local response=$(curl -s -X POST "$DEPLOY_ENDPOINT" \
        -H "Content-Type: application/gzip" \
        -H "X-Framework: $framework" \
        --data-binary "@$tarball_path")

    # Cleanup temporary tarball
    if [[ "$cleanup_tarball" == true ]]; then
        rm -f "$tarball_path"
    fi

    # Parse response
    local preview_url=$(echo "$response" | grep -o '"previewUrl":"[^"]*"' | cut -d'"' -f4)
    local claim_url=$(echo "$response" | grep -o '"claimUrl":"[^"]*"' | cut -d'"' -f4)
    local deployment_id=$(echo "$response" | grep -o '"deploymentId":"[^"]*"' | cut -d'"' -f4)
    local project_id=$(echo "$response" | grep -o '"projectId":"[^"]*"' | cut -d'"' -f4)
    local error=$(echo "$response" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)

    if [[ -n "$error" ]]; then
        echo "Error: $error" >&2
        exit 1
    fi

    if [[ -z "$preview_url" ]]; then
        echo "Error: Deployment failed - no preview URL returned" >&2
        echo "Response: $response" >&2
        exit 1
    fi

    # Output results
    echo "" >&2
    echo "Deployment successful!" >&2
    echo "Preview URL: $preview_url" >&2
    echo "Claim URL: $claim_url" >&2
    echo "" >&2

    # Return JSON for programmatic use
    cat <<EOF
{
  "previewUrl": "$preview_url",
  "claimUrl": "$claim_url",
  "deploymentId": "$deployment_id",
  "projectId": "$project_id"
}
EOF
}

# Run deployment
deploy "$@"
