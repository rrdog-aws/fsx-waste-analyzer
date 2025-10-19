# 🧠 FSx Waste Analyzer

The **FSx Waste Analyzer** is a serverless tool designed to analyze **Amazon FSx for NetApp ONTAP** environments and identify **capacity inefficiencies, low IO volumes, cost optimization opportunities, and compliance gaps** (e.g., encryption).

It provides actionable recommendations and generates a detailed **interactive HTML report** that highlights potential storage waste, throughput issues, and efficiency metrics across your FSx file systems and volumes.

---

## 🚀 Overview

This solution includes two main components:

1. **AWS Lambda Function** (Python 3.x):
   - Collects FSx for ONTAP metadata, CloudWatch performance metrics, and pricing information.
   - Performs analysis to detect inefficiencies and generate recommendations.
   - Outputs a formatted **HTML report** summarizing findings.

2. **Static Front-End (HTML/JS):**
   - Provides a simple user interface hosted via S3 or API Gateway.
   - Invokes the Lambda function via API Gateway and displays the HTML report dynamically.

---

## 🏗️ Architecture

+-------------+ +----------------+ +-------------+
| Web Client | <-----> | API Gateway | <------> | Lambda |
| (index.html)| | (Invoke URL) | | FSx Analyzer|
+-------------+ +----------------+ +-------------+
|
|
+------------------+
| Amazon FSx |
| CloudWatch, etc. |
+------------------+


---

## ⚙️ Lambda Function

### **Key Features**
- Analyzes **FSx for ONTAP Gen-1** file systems.
- Calculates:
  - Storage efficiency
  - I/O throughput (95th percentile)
  - Slack space (unused capacity)
  - Cost estimates based on AWS Pricing API
- Identifies and recommends:
  - Underutilized or cold volumes
  - Over/under-provisioned throughput
  - Encryption compliance
  - Storage efficiency tuning opportunities
- Generates an HTML report with collapsible tables and color-coded recommendations.

### **Environment Variables**

| Variable | Description | Default |
|-----------|--------------|----------|
| `REGION` | AWS Region for FSx query | `eu-west-1` |
| `LOOKBACK_DAYS` | Days to look back for metrics | `3` |
| `PERIOD` | CloudWatch metric period (seconds) | `840` |
| `PCTL` | Percentile used for I/O analysis | `95` |
| `FSID` | Optional FSx ID to target a single filesystem | *(all)* |
| `TOP_VOLS` | Limit to top N volumes by size | `0` (all) |

---

## 🌐 Front-End

The included HTML page (`index.html`) provides a **simple and modern UI** for running the FSx analysis.

### **Features**
- “Run FSx Analysis” button to trigger Lambda via API Gateway.
- Loading spinner and error handling.
- Embeds the full HTML report returned by Lambda.
- No dependencies or frameworks — pure HTML, CSS, and JS.

### **Configuration**
Replace the placeholder API endpoint in the HTML:
```javascript
const response = await fetch('https://YOUR_API_GATEWAY_URL.amazonaws.com/prod');

Hosting Options

You can host the front-end:
On an S3 static website bucket
Via CloudFront for secure distribution
As a custom domain with Route53 + SSL