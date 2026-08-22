# ECHO Purpose-Specific Form Design Contract

Status: design authority for the canonical `web/forms/` lane. Shared primitives are allowed; shared page composition is not presumed.

## Common doctrine

Every form must answer a distinct business job. Reuse may cover typography, cells, lookup adapters, review/save, evidence, print/export and accessibility primitives. Reuse must not force identical field order, grid geometry, navigation routes, mobile composition or review documents across different jobs.

All forms use one authenticated context model: current date, branch and actual login user are defaults. Context is visible compactly and editable through a context drawer when authority permits. Consequential changes retain actual principal, selected branch/person and reason.

All forms support: local draft continuity; database lookup adapters; explicit review before consequential save/issue; revision history; mobile image projection; A4 PDF projection; and task-specific navigation. Screen view, mobile image and A4 PDF are separate projections of one saved record.

Desktop target: purpose-fit working composition without disproportionate empty space or gratuitous full-width stretching. Mobile target: primarily vertical movement, no routine horizontal scrolling, 16px editable text where iOS focus zoom would otherwise disturb layout, and controls near the current task.

## 1. Closing Cash

**Primary question:** What came in/out of the cash plane today, what physical cash remains, and does it reconcile?

**Main entities:** Sale amount, bill/reference, expense/cash movement amount, particulars/source, opening cash, denomination count, closing reconciliation.

**Working geometry:** Excel-inspired four-column entry grid. SALE and EXPENSES are narrow amount columns; BILL is narrow reference; PARTICULARS is moderately wider, never residual full-browser width. Cash Count and Closing sit beside the grid on desktop and immediately below it on mobile.

**Navigation:** SALE -> BILL -> next SALE; EXPENSES -> PARTICULARS -> next EXPENSE; denomination Qty -> next denomination. Navigation derives from active column, never mode state.

**Review:** exact day sheet + physical count + formula chain + difference + context. Yellow-column values remain raw cash-plane evidence until Prism classifies their business meaning.

## 2. Invoice / Sale

**Primary question:** Who is buying what, in what quantity, at what authorized price/tax, and what is the amount to issue?

**Main entities:** Party/customer, contact/GST identity as applicable, item/product, quantity, unit, rate, discount/price authority when applicable, GST, line amount, payment mode/evidence, invoice number/series.

**Working geometry:** customer/party is the first dominant lookup; item entry is the dominant repeated action. Desktop uses customer strip/rail plus compact item table and live totals. Mobile uses a vertical sales workstream optimized for repeated product selection and quantity/rate entry, not a generic form card stack.

**Navigation:** Customer -> Item -> Qty -> Rate -> next Item for fast cash-counter use; secondary fields are accessible without interrupting the common path.

**Review:** branded invoice projection with taxable value, GST, total, payment evidence and ECHO/BUSY series state.

## 3. Estimate

**Primary question:** What may this job/sale cost if the customer proceeds?

**Main entities:** Party/customer, intended item/work, quantity, unit, indicative/editable rate, optional discount, tax treatment, validity, assumptions/notes.

**Design distinction from Invoice:** no payment collection workflow, no issued-sale semantics, no stock deduction. Price editing and explanatory notes are more prominent. The user should be able to assemble possibilities quickly.

**Navigation:** Party -> Item/work -> Qty -> Rate -> next item, with easy note/assumption access.

**Review:** clearly marked ESTIMATE with validity and non-invoice status.

## 4. Quotation

**Primary question:** What formal commercial offer is TAGRO making to a named party?

**Main entities:** Party/firm, address/contact/GST identity, quotation reference, item description, quantity, unit, commercial rate, discount if authorized, GST, terms, validity, delivery/payment terms.

**Design distinction from Estimate:** stronger party/document identity and terms; formal document preview is more important and may remain visible beside entry on wide desktop. The output must follow approved TAGRO quotation design language.

**Navigation:** Party -> commercial lines -> terms -> Review.

## 5. Purchase / Purchase Entry

**Primary question:** What did we buy, from whom, at what landed/commercial cost, and what source document proves it?

**Main entities:** Supplier, supplier invoice/date, item, quantity, unit, purchase rate, tax, freight/other acquisition cost where relevant, branch/location received, payment/credit status.

**Working geometry:** item and cost dominate; supplier/source invoice remains continuously visible. The grid is not a reversed sales invoice: purchase cost evidence and receiving state are first-class.

**Navigation:** Supplier/source -> Item -> Qty -> Purchase Rate -> tax/cost if needed -> next Item.

**Review:** purchase evidence sheet / purchase voucher projection, not a customer invoice.

## 6. Stock Count

**Primary question:** What physical quantity was actually observed here, now, and how does it compare with references/history?

**Main entities:** Location, part/item, physical counted quantity, optional condition/bin, expected/reference quantity, variance, counter/person, recount state, evidence note.

**Working geometry:** counted quantity is the dominant entry target. Expected stock is visually secondary/reference-only. Historical/other-branch signals belong in a side evidence plane, not in the count cell.

**Navigation:** Item -> Count -> next Item. Recount/variance review is a separate route.

**Review:** immutable count event set, reference variance, confidence/review signals. A count is temporary truth/evidence until admitted through the stock-history plane.

## 7. Service Record

**Primary question:** What machine did this party bring, what did they report, what did TAGRO observe/diagnose, what work/parts were required and done, and what was billed?

**Main entities:** Party/customer, phone, machine identity, brand, model, serial number, machine type, complaint in customer words, observed condition, diagnosis, required job, required parts, approval/estimate, work done, parts used, technician, status/timestamps, invoice number, invoice amount, service charge, delivery/closure evidence.

**Working geometry:** broader than transactional forms. It is a staged record with persistent identity header (customer + machine + serial/model) and progressive sections: Intake -> Observation -> Diagnosis/Approval -> Work/Parts -> Billing/Closure. Parts/work tables may repeat, but the page is not a generic item invoice.

**Mobile:** one vertical staged workstream with the machine identity compactly pinned or easily recalled; sections collapse after completion while preserving state.

**Review:** complete service record plus customer acknowledgement / closure projection as applicable.

## 8. Receipt / Income

**Primary question:** What money came in, how much, and what is its source/claim?

**Main entities:** Amount is primary; source can be invoice, cash box, customer/party, branch transfer, service receipt, bank/UPI/card reference or other source; receiving account/cash box; narration/evidence; payer when known.

**Design distinction:** this is not merely `party + amount`. Source identity is co-primary because a credit is not automatically income and cash movement is not automatically revenue.

**Navigation:** Amount -> Source type/reference -> Party/source -> receiving mode/account -> narration if needed.

**Review:** receipt evidence showing source classification separately from accounting interpretation.

## 9. Payment / Expense

**Primary question:** What money went out, how much, to whom/what purpose, and from which cash/bank source?

**Main entities:** Amount is primary; payee/party, purpose/item/head, source account/cash box, mode/reference, supporting invoice/bill if any, narration/evidence, approval where required.

**Design distinction:** this is not a mirror image of Receipt. Purpose/expense head and payment source are more prominent; supplier payment, transfer, owner movement, capital spend and operating expense must remain distinguishable evidence states.

**Navigation:** Amount -> Purpose/item -> Payee -> source/mode -> reference/narration.

**Review:** payment evidence with purpose and source clearly separated; Prism/accounting classification may follow but must not be silently inferred from debit direction alone.

## Rejected generic assumptions

- Invoice, Estimate and Quotation must not share one page merely because they all contain item/qty/rate.
- Receipt and Payment must not share one page merely because both contain party/amount/mode.
- Purchase must not be treated as sales with labels reversed.
- Service must not be reduced to customer fields plus a four-column technician table.
- Stock Count must not make expected stock visually equal to physical count evidence.
- Mobile must not be desktop tables squeezed or cardified by a universal CSS transform.

## Visual and navigation acceptance gates

For every form before field trial:
1. 1366x768 laptop inspection: common task fits without disproportionate whitespace or accidental horizontal scroll.
2. 390x844 phone inspection: primary path flows vertically; no routine side-scroll.
3. Focus does not cause unexpected viewport displacement.
4. Return/Enter follows the form-specific path from the actual active field.
5. Tab remains conventional on desktop.
6. Primary value/entity receives strongest visual weight; secondary context is quieter.
7. Review faithfully represents the pending saved record.
8. Mobile image and A4 PDF are independently composed from the same record and use TAGRO template identity.
9. Database suggestions remain assistive; manual entry and provenance remain possible where policy allows.
10. No form is admitted because a generic renderer can technically display it; its human task must be validated.
