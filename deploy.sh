#!/bin/bash
# GigNav - Deployment Script (Cloud Automation Bonus)
# This script sets up the environment and deploys GigNav

set -e

echo "🚀 GigNav Deployment Script"
echo "=========================="

# Check environment
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "❌ GOOGLE_CLOUD_PROJECT not set"
    exit 1
fi

echo "📋 Project: $GOOGLE_CLOUD_PROJECT"

# Enable required APIs
echo "🔧 Enabling Google Cloud APIs..."
gcloud services enable bigquery.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
gcloud services enable aiplatform.googleapis.com --project=$GOOGLE_CLOUD_PROJECT

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium

# Upload data to BigQuery
echo "📊 Uploading DCWP data to BigQuery..."
python upload_to_bq.py

echo ""
echo "✅ GigNav is ready!"
echo "   Run: python web_agent.py"
