# Europe Job Scraper API Documentation

This document explains the query parameters available for the primary `GET /api/v1/jobs` endpoint.

## Endpoint
`GET /api/v1/jobs`

This endpoint dynamically connects to the specified ATS source, scrapes the active job board for the provided company, applies any requested filters, and returns a unified JSON array of `JobSchema` objects.

---

## Required Parameters

These parameters must be provided in every request, otherwise the API will return a `422 Unprocessable Entity` error.

| Parameter | Type | Required | Description | Example |
| :--- | :--- | :---: | :--- | :--- |
| **`source`** | `string` | ✅ Yes | The target Applicant Tracking System (ATS) to scrape. The factory currently supports specific engines. | `greenhouse`, `lever`, `smartrecruiters`, `personio`, `ashby`, `linkedin` |
| **`company`** | `string` | ✅ Yes | The unique identifier or "slug" the company uses on their ATS board. This is usually found in the URL of their careers page. | `contentful` (for Greenhouse), `smartrecruiters` (for SmartRecruiters) |

---

## Optional Filter Parameters

These parameters allow you to filter the scraped results. 

> [!NOTE]
> **Filtering Behavior:** Depending on the ATS, these filters are either applied natively during the HTTP request (to save bandwidth) or applied locally in memory after fetching all jobs from the board.

| Parameter | Type | Required | Description | Example |
| :--- | :--- | :---: | :--- | :--- |
| **`keyword`** | `string` | ❌ No | Searches for a specific word or phrase within the job title. It is case-insensitive. | `engineer`, `marketing`, `ai` |
| **`country`** | `string` | ❌ No | Filters jobs that are located in a specific country. | `Germany`, `United Kingdom` |
| **`city`** | `string` | ❌ No | Filters jobs that are located in a specific city. | `Berlin`, `London` |
| **`remote`** | `boolean` | ❌ No | If set to `true`, only returns jobs that are explicitly marked as Remote or Work-From-Home. | `true`, `false` |
| **`salary_min`** | `number` | ❌ No | Filters out jobs where the maximum salary listed is below this minimum threshold. (Only applies to jobs where salary data was successfully scraped). | `80000`, `120000.50` |
| **`employment_type`** | `string` | ❌ No | Filters by the type of contract. | `Full-time`, `Part-time`, `Contract` |
| **`page`** | `integer` | ❌ No | Pagination control. Defaults to `1`. Note: Only some ATS systems (like SmartRecruiters) require pagination; others return all jobs on page 1. | `1`, `2`, `3` |

---

## Example Usage

**cURL Example:**
Fetching remote engineering jobs at Contentful:
```bash
curl -X GET "http://localhost:8000/api/v1/jobs?source=greenhouse&company=contentful&keyword=engineer&remote=true" -H "accept: application/json"
```

**JavaScript (Fetch) Example:**
```javascript
const url = new URL("http://localhost:8000/api/v1/jobs");
url.searchParams.append("source", "greenhouse");
url.searchParams.append("company", "contentful");
url.searchParams.append("keyword", "engineer");

const response = await fetch(url);
const jobs = await response.json();
console.log(jobs);
```
