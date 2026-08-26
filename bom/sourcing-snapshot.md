# Sourcing snapshot — 2026-08-22 UTC

This file records what was actually checked while preparing the issue #3 schematic. It is not a quotation, purchase order, lifecycle guarantee, or fabrication status.

## Live LCSC product-page observations

The following public product pages were fetched on 2026-08-21–22 UTC. The first published price break and displayed stock were copied into the KiCad symbol properties and exported BOM.

| LCSC | MPN | First price break | Displayed stock | Source |
|---|---|---:|---:|---|
| C5180029 | NAU7802SGI | 1 @ $1.7781 | 1,427 | https://www.lcsc.com/product-detail/C5180029.html |
| C3020560 | USB4105-GF-A | 1 @ $1.0659 | 926 | https://www.lcsc.com/product-detail/C3020560.html |
| C189895 | SM04B-GHS-TB(LF)(SN) | 1 @ $1.1182 | **0** | https://www.lcsc.com/product-detail/C189895.html |
| C17313 | MF-MSMF050-2 | 10 @ $0.0668 each | 47,400 | https://www.lcsc.com/product-detail/C17313.html |
| C15759 | B140-13-F | 5 @ $0.0856 each | 59,660 | https://www.lcsc.com/product-detail/C15759.html |
| C107696 | RC0603FR-07220RL | 100 @ $0.0061 each | 417,400 | https://www.lcsc.com/product-detail/C107696.html |
| C3335156 | TSW-104-07-G-S | 1 @ $0.6472 | 337 | https://www.lcsc.com/product-detail/C3335156.html |
| C97949 | GRM31CR61A106KA01L | 1 @ $0.3351 | 22 | https://www.lcsc.com/product-detail/C97949.html |
| C5555828 | ASMT-YTC7-0AA02 | 1 @ $1.7772 | 79 overseas stock | https://jlcpcb.com/partdetail/BroadcomLimited-ASMT_YTC70AA02/C5555828 |

J2's preferred LCSC listing was out of stock and is explicitly flagged in the schematic/BOM. An alternate source must be verified before ordering.

The original draft selected ASMT-YTC2-0AA02, which a current authorized-distributor lookup identified as obsolete. It was replaced with ASMT-YTC7-0AA02. Broadcom AV02-3819EN confirms the same 3.0 × 2.8 mm PLCC-6 geometry and exact lead sequence used by the KiCad symbol/footprint; JLCPCB listed C5555828 as an in-stock extended part on 2026-08-22 UTC.

## Other lines

DigiKey and manufacturer pages were discoverable, but no distributor API credentials were available in the scheduled environment and DigiKey blocked automated price/stock retrieval. Those BOM costs are clearly marked as public-listing/search **estimates**, and stock is marked unverified rather than invented. Re-check all such lines before ordering. The Seeed module price is the public direct-store list price observed during this review.

`bom/non-schematic-items.csv` deliberately uses `TBD` wherever an enclosure, harness, supply, or hardware choice has not been sourced. No stock, price, assembly, prototype, or fabrication result is claimed for those items.

## Layout-milestone public-search refresh — 2026-08-26T00:25:19Z

Public search results were refreshed for the four layout-critical assembled parts. Search-index snippets are transient and sometimes disagree, so this was not treated as an API-backed quote and the dated quantity-one observations in KiCad were not overwritten:

- C3020560 / USB4105-GF-A: the exact LCSC result reported “in stock” and “from $0.6043”; another indexed URL reported $0.6584. No exact stock count was exposed.
- C5180029 / NAU7802SGI: the exact LCSC result reported “in stock” and “from $0.8277”; a category URL reported $0.8792. No exact stock count was exposed.
- C189895 / SM04B-GHS-TB(LF)(SN): exact and category results both reported “in stock,” but indexed prices conflicted ($1.0754 versus $0.2887). The BOM retains its dated out-of-stock observation and requires checkout-time verification rather than converting an unstable snippet into a sourcing claim.
- 113991054 / XIAO ESP32-C3: the manufacturer page reported USD $4.99 and “1+ in stock”; LCSC still mapped the MPN to C18212168 without exposing a defensible quantity/price in the result.

The local LCSC resolver was not used because it required accepting bulk-catalog terms on the user's behalf. Current public observations must still be rechecked immediately before ordering.
