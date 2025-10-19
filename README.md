# 🧠 FSx Waste Analyzer

![AWS](https://img.shields.io/badge/AWS-FSx-orange?logo=amazon-aws)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)

---

## 🏗️ Overview

The **FSx Waste Analyzer** is a serverless tool designed to analyze **Amazon FSx for NetApp ONTAP** environments and identify:

- Capacity inefficiencies  
- Low I/O volumes  
- Cost optimization opportunities  
- Compliance gaps (e.g., encryption status)

It provides actionable recommendations and generates an interactive **HTML report** summarizing your FSx usage, waste, and optimization potential.

---

## 🚀 Architecture



---

## ⚙️ Components

### 1. AWS Lambda Function (Python)
- Collects FSx and CloudWatch metrics
- Calculates:
  - Storage efficiency
  - I/O throughput (95th percentile)
  - Slack space (unused capacity)
  - Cost estimates from AWS Pricing API
- Generates HTML reports with visual indicators and recommendations

### 2. Front-End (Static HTML/JS)
- Simple UI to trigger the Lambda via API Gateway  
- Displays the HTML report dynamically  
- No dependencies — built with pure HTML, CSS, and JavaScript

---

## 🔧 Lambda Configuration

### Environment Variables

| Variable | Description | Default |
|-----------|--------------|----------|
| REGION | AWS Region for FSx query | eu-west-1 |
| LOOKBACK_DAYS | Days to look back for metrics | 3 |
| PERIOD | CloudWatch metric period (seconds) | 840 |
| PCTL | Percentile used for I/O analysis | 95 |
| FSID | Optional FSx ID to target a single filesystem | *(all)* |
| TOP_VOLS | Limit to top N volumes by size | 0 (all) |

---

## 🌐 Front-End Configuration

Replace the placeholder API endpoint in `index.html` with your API Gateway invoke URL:

```javascript
const response = await fetch('https://YOUR_API_GATEWAY_URL.amazonaws.com/prod');





