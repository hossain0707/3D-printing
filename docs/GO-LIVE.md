# Commercial Launch Gate — What is Still Required

The public deployment is a **real functioning customer design preview and print-candidate exporter**, but not a complete transaction service. This distinction is intentional.

## Live now
- Polished mobile storefront / landing page, local photo processing, optional CPU AI landmarks, real 3D character preview.
- Customization, regenerate, version approval, downloadable 3D and texture bundle.
- Example retail prices are explicitly illustrative.

## Not connected (must be completed for paid orders)
1. Dedicated private database and object storage. Do not reuse an unrelated application's database.
2. Authenticated server API, rate limits, image security checks, model retention/deletion policies.
3. Customer checkout via a properly registered payment gateway; never pretend payment succeeded.
4. Durable customer and operator accounts; secure admin production/order dashboard and audit logging.
5. Quote and print-vendor integration, supplier SLA, output tolerances, material/finish/color profile.
6. Email/SMS/Kakao notifications with verified senders; shipping carrier tracking.
7. Refund/cancellation/defect/reprint handling and consumer disclosures.
8. Korean business registration, sales/tax requirements and immigration/work authorization (as applicable).
9. Legal review of personal photo consent, data processing disclosures and 3rd-party IP permissions.
10. E2E accessibility/performance/security checks, real device testing, and physical print QA on at least 3-5 representative figures.

## Estimated go-live maturity (not dates)
- **Prototype:** UI and on-device processing; exists now.
- **Factory validation:** print vendor import → mesh repair → first article → color/sample approval; incomplete.
- **Commerce enablement:** operator authentication, persistent orders, payment and dispatch; incomplete.
- **Ongoing operations:** fulfillment alerts, inventory, privacy audits and customer support; incomplete.

## Suggested vendor onboarding fields
- Business name/contact
- Supported colored formats and texture packaging (OBJ/MTL/PNG, 3MF etc.)
- Full-color technology and color management (sRGB, ICC profile)
- Minimum wall thickness / hole diameter / minimum details
- Per-figure print price at 50, 80 and 100 mm
- Bulk volume price, support removal and coating/finish fees
- Reprint/warranty terms and packaging options

## Security policy
Never store client photographs in a public repository or Vercel source bundle. Store in private authenticated storage only after consent and a retention policy. Do not include service-role keys, signing keys or payment credentials in browser JavaScript or public env variables.
