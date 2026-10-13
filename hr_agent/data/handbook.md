# Northwind HR Handbook (fictional, for the Week 7 exercise)

General policy clauses. All entitlements are evaluated as of 2026-10-01 and are in days.
Per-jurisdiction entitlement tables live in jurisdiction_rules.json (get_jurisdiction_rules).

## HB-1 Tenure
Tenure is the number of completed months of continuous service with Northwind as of the question
date. Service in any Northwind jurisdiction counts, so a transfer between offices keeps tenure.

## HB-2 Transfers between jurisdictions
When an approved transfer takes effect, the destination jurisdiction's rules apply to every
entitlement (annual leave, sick leave, notice period). Questions about entitlements after the move
must be answered with the destination jurisdiction's rules and the employee's full tenure.

## HB-3 Contractors
Contractors are not employees under this handbook. Every handbook entitlement (annual leave,
sick leave, notice period) for a contractor is 0 days; the individual contract governs instead.

## HB-4 Annual leave carry-over
Up to 5 unused annual leave days may be carried into the next year. Carried-over days are added
to the current year's entitlement when computing the remaining balance:
balance = entitlement + carry_over_days - annual_leave_taken_days.

## HB-5 Probation
The first 6 months of service are probation. Probation-specific values appear in the jurisdiction
tables where they differ.

## HB-6 Part-time employees
Part-time annual leave and sick leave entitlement is the full-time entitlement multiplied by the
employee's FTE, rounded down to the nearest half day. Notice periods are not pro-rated.
