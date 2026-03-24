# Power BI Apps — Setup & Publishing Guide

This guide covers creating, configuring, publishing, and maintaining Power BI Apps for the Contoso Global Retail & Supply Chain environment.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Creating an App](#creating-an-app)
4. [Configuring Sections & Navigation](#configuring-sections--navigation)
5. [Setting Up Audiences](#setting-up-audiences)
6. [Auto-Install Configuration](#auto-install-configuration)
7. [Publishing & Updating](#publishing--updating)
8. [Mobile Optimization](#mobile-optimization)
9. [Sensitivity Labels & Security](#sensitivity-labels--security)
10. [Terraform / API Automation](#terraform--api-automation)
11. [Contoso App Inventory](#contoso-app-inventory)

---

## Overview

Power BI Apps bundle multiple reports, dashboards, scorecards, and paginated reports into a single installable package. End users install the app from the Power BI app marketplace and get a curated, branded experience with custom navigation — without needing direct workspace access.

**Key benefits:**
- **Curated experience:** Users see organized content with custom sections, not a raw workspace file list
- **Access control:** App permissions are independent of workspace permissions
- **Auto-install:** Push the app to Entra ID security groups automatically
- **Branding:** Custom logo, colors, and navigation match the Contoso brand
- **Update policy:** Choose between automatic updates or user-controlled updates

---

## Prerequisites

- Power BI **Pro** or **Premium Per User (PPU)** license for the publisher
- Reports and semantic models published to a Fabric workspace backed by **Premium capacity** (F8+) or PPU
- Entra ID security groups created for each target audience
- (For auto-install) Power BI admin must enable "Push apps to end users" in the admin portal

### Admin Portal Settings

Navigate to **Power BI Admin Portal → Tenant settings** and enable:
- ✅ Publish content packs and apps to the entire organization
- ✅ Push apps to end users
- ✅ Allow users to install Power BI apps automatically

---

## Creating an App

### Via Power BI Portal

1. Navigate to the workspace containing your reports (e.g., `contoso-analytics-prod`)
2. Click **Create app** in the top toolbar
3. Fill in the **Setup** tab:
   - **App name:** e.g., "Contoso Retail Operations"
   - **Description:** Brief description for the app marketplace
   - **App logo:** Upload the Contoso logo (PNG, 45×45px minimum)
   - **Theme color:** `#0078D4` (Contoso primary blue)
   - **Support site:** Link to the support SharePoint page
   - **Contact email:** Team distribution list
4. Click **Next** to proceed to content configuration

### Via REST API

```bash
# Create an app from a workspace
POST https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/CreateApp

# Request body
{
  "name": "Contoso Retail Operations",
  "description": "Complete operational intelligence for store managers and regional directors.",
  "targetWorkspaceId": "{workspace_id}"
}
```

---

## Configuring Sections & Navigation

### Adding Sections

In the **Content** tab of the app editor:

1. Click **+ New section** to create a navigation group
2. Name the section (e.g., "Daily Operations", "Supply Chain")
3. Choose an icon from the built-in icon library
4. Drag reports, dashboards, and scorecards into the section
5. Reorder items within a section by dragging

### Adding Individual Items

1. Click **+ Add content** within a section
2. Select the content type: Report, Dashboard, Scorecard, or Link
3. For reports: choose the workspace and report, then optionally select a specific page
4. For external links: enter the URL (useful for linking to SharePoint, documentation, etc.)

### Navigation Customization

- **Show descriptions:** Toggle to show/hide item descriptions in the nav panel
- **Default landing:** Set which item appears when the app first opens
- **Section icons:** Choose icons that represent each section's purpose

### Example: Contoso Retail Operations Sections

| Section | Icon | Items |
|---------|------|-------|
| Daily Operations | 🏪 StoreMirrored | Executive Dashboard, Sales Analytics |
| Supply Chain | 🚛 DeliveryTruck | Inventory Operations, Supply Chain Scorecard |
| Customer Intelligence | 👥 People | Customer Insights |

---

## Setting Up Audiences

### Access Groups

In the **Audience** tab:

1. Click **+ New audience** (or use the default audience)
2. Name the audience (e.g., "Store Managers")
3. Add Entra ID security groups:
   - Search by group name (e.g., `contoso-store-managers`)
   - Select and add the group
4. Set permissions for the audience:
   - **Viewer:** Can view all content in the app
   - **Member:** Can view + create personal bookmarks + subscribe to reports

### Multiple Audiences

You can create different audiences with different content visibility:

| Audience | Groups | Visible Sections |
|----------|--------|-----------------|
| Store Managers | contoso-store-managers | Daily Operations, Inventory |
| Regional Directors | contoso-regional-directors | All sections |
| VP Operations | contoso-vp-operations | All sections |

> **Note:** Different audiences can see different subsets of content. Configure this in the audience settings by toggling section visibility per audience.

---

## Auto-Install Configuration

Auto-install pushes the app directly to users' Power BI home without requiring them to find and install it.

### Enable Auto-Install

1. In the **Audience** tab, check **Install this app automatically**
2. Select which security groups should get auto-install
3. Publish the app

### Requirements

- The Power BI admin must have enabled "Push apps to end users" in tenant settings
- The workspace must be backed by Premium capacity or PPU
- Security groups must be **Entra ID security groups** (not Microsoft 365 groups)

### Behavior

- New group members get the app installed within ~24 hours of being added to the group
- Users can uninstall the app, but it will be reinstalled if they remain in the group
- Updates to the app are pushed automatically if the update policy is set to "Automatic"

---

## Publishing & Updating

### Initial Publish

1. Complete all tabs: Setup, Content, Audience
2. Click **Publish app**
3. The app appears in the Power BI app marketplace and is auto-installed for configured groups

### Updating an Existing App

1. Navigate to the workspace → click **Update app**
2. Make changes to content, sections, or audiences
3. Click **Update app** to push changes

### Update Policies

| Policy | Behavior |
|--------|----------|
| **Automatic** (recommended) | Users always see the latest version immediately after publishing |
| **Allow users to get the old and new version** | Users are notified and can choose when to update |

For Contoso, we use **Automatic** for all apps — executives and field workers should always see current data.

---

## Mobile Optimization

### Creating Mobile Layouts

1. Open a report in Power BI Desktop or the web editor
2. Switch to **Phone layout** view (View → Phone layout)
3. Drag visuals from the desktop layout onto the phone canvas
4. Resize for vertical scrolling (stack visuals vertically)
5. Publish to the workspace

### Mobile-Specific Considerations

- **Large tap targets:** Ensure buttons and slicers are at least 44×44px
- **Simplified visuals:** Use cards and KPIs over complex tables on mobile
- **Offline caching:** Users on the Power BI mobile app can view cached reports without connectivity
- **Dark mode:** Test your reports in dark mode (Power BI mobile supports it)
- **Push notifications:** Configure data-driven alerts to send push notifications to mobile users

### Offline Access

To enable offline access in the Power BI mobile app:

1. Users open the app on their mobile device
2. Reports are automatically cached during the sync interval
3. When offline, users see the last-cached version with a "Last updated" timestamp
4. Data refreshes automatically when connectivity returns

---

## Sensitivity Labels & Security

### Applying Sensitivity Labels

1. In the **Setup** tab, select the sensitivity label:
   - **Public:** No restrictions
   - **Internal:** Contoso employees only
   - **Confidential:** Restricted to specific groups
   - **Highly Confidential:** Executive only, watermarked, encrypted
2. The label inherits from Microsoft Purview Information Protection

### Contoso App Labels

| App | Sensitivity Label |
|-----|------------------|
| Contoso Retail Operations | Internal |
| Contoso Executive Suite | Highly Confidential |
| Contoso Field Operations | Internal |

---

## Terraform / API Automation

### Current State

As of the `microsoft/fabric` Terraform provider ~> 1.8, there is **no dedicated `fabric_power_bi_app` resource**. Power BI Apps are managed through:

1. **Power BI Portal** — Manual creation and publishing (recommended for initial setup)
2. **Power BI REST API** — Programmatic creation and updates
3. **Power BI Management cmdlets** — PowerShell automation

### REST API Endpoints

```
# List apps in a workspace
GET https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/apps

# Create/update an app
POST https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/CreateApp

# Update app access (add users/groups)
POST https://api.powerbi.com/v1.0/myorg/apps/{app_id}/users

# Get app details
GET https://api.powerbi.com/v1.0/myorg/apps/{app_id}
```

### GitHub Actions Integration

The app definition JSON files in `src/power-bi/apps/` can be consumed by a GitHub Actions workflow that:

1. Reads the JSON configuration
2. Calls the Power BI REST API to create/update the app
3. Configures audiences and auto-install settings
4. Publishes the app

See `.github/workflows/` for CI/CD integration patterns.

---

## Contoso App Inventory

| App | File | Audience | Sensitivity |
|-----|------|----------|-------------|
| Contoso Retail Operations | `contoso_retail_app.json` | Store Managers, Regional Directors, VP Ops | Internal |
| Contoso Executive Suite | `contoso_executive_app.json` | C-Suite, SVP Leadership | Highly Confidential |
| Contoso Field Operations | `contoso_field_app.json` | Technicians, Drivers, Warehouse Workers | Internal |
