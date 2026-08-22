# TAGRO × ECHO OS — External Services Dock V1

Status: candidate under WO-0013
Date: 2026-08-22

## Purpose

ECHO may use external logistics and payment providers without making any provider the operational source of truth.

The governing pattern is:

`ECHO event -> governed command -> provider adapter -> provider request -> provider acknowledgement/event -> ECHO reconciliation`

A provider acknowledgement is evidence about an external consequence. It does not rewrite the originating ECHO sale/order/payment/shipment event.

## Shared adapter rules

Every provider adapter must declare:
- provider identity and environment;
- supported capabilities;
- request/response schema mapping;
- idempotency/retry behavior;
- authentication/secret boundary;
- callback/webhook verification;
- provider reference IDs;
- raw provider evidence retention;
- normalized ECHO event mapping;
- failure/reconciliation behavior;
- replacement/migration behavior.

Provider credentials must never be stored in browser/PWA source or client local storage. Calls requiring secrets originate at the governed server boundary.

## Logistics dock

### ECHO-owned truth

ECHO owns:
- customer/order identity;
- dispatch intent;
- package/item relationship;
- requested service level;
- origin/destination context;
- who authorised dispatch;
- shipment-provider selection decision;
- shipment lifecycle as reconciled from provider evidence.

### Provider-owned evidence

A carrier may establish provider-specific facts such as:
- serviceability/rate quote;
- waybill/shipment ID;
- label;
- pickup request/confirmation;
- carrier scan/tracking events;
- NDR event/status;
- delivered/return-to-origin provider event;
- carrier charge.

Queued or requested does not equal booked. Booked does not equal picked up. Picked up does not equal delivered.

### Carrier adapter candidates

#### Amazon Shipping India

Candidate capabilities supported by current public Amazon Shipping material include direct API integration for orders from a merchant's own website/other marketplaces, rates, labels, automated order management, tracking, and NDR workflows.

Model as `carrier.amazon_shipping` behind the common logistics contract.

#### Delhivery

Candidate capabilities documented by Delhivery include pincode serviceability, waybill fetch, warehouse creation/update, shipment creation/update, tracking, shipping-cost calculation, label generation, pickup request and NDR update.

Model as `carrier.delhivery` behind the same contract.

### Carrier selection

ECHO may later compare eligible providers by serviceability, price, promised delivery, COD/prepaid support, pickup availability and observed performance. Automatic recommendation may be Observer output. Actual dispatch/provider booking remains Driver-authorised.

## Payment dock

### ECHO-owned truth

ECHO owns:
- sale/invoice/service/customer context;
- amount requested;
- receiving enterprise/counter;
- actor initiating payment request;
- expected purpose/allocation;
- admitted payment evidence and its relationship to the sale/customer/account;
- reconciliation state.

### Payment-provider evidence

A payment service may establish:
- payment order/link/intent/QR reference;
- customer payment attempt;
- provider payment ID;
- authorised/success/failed state;
- refund reference;
- settlement evidence where supported;
- webhook/callback evidence.

Displaying a QR or opening a UPI app does not equal payment. Browser redirect does not establish payment. ECHO must verify provider-side success through a signed/verified server-side result or subsequent provider readback before treating payment as confirmed.

### UPI direction

UPI should be integrated through a replaceable payment-service adapter rather than embedding a static merchant QR as proof of payment.

Initial candidate provider: Razorpay, because its current API supports test/live payment-gateway flows and UPI Intent/QR. The provider is not constitutionally preferred and can be replaced by another admitted PSP/payment gateway.

Important current rule: legacy UPI Collect by manually entering a VPA is deprecated for most ordinary merchant flows from 28 February 2026. New ECHO work should therefore target UPI Intent and/or QR flows rather than building around manual VPA collect.

Model candidate as `payment.razorpay` behind a provider-neutral payment contract.

## Suggested normalized states

### Logistics
`dispatch_draft -> booking_requested -> carrier_booked -> pickup_requested -> picked_up -> in_transit -> delivery_exception/ndr -> delivered | return_in_transit -> returned`

Provider-specific event codes remain preserved separately.

### Payment
`payment_request_draft -> provider_intent_created -> customer_action_pending -> provider_success | provider_failed -> echo_verified -> allocated/reconciled -> settlement_observed`

Do not collapse `provider_success`, `echo_verified`, allocation and settlement into one state.

## UI implications

Sale completion may offer:
- PAY NOW / SEND PAYMENT LINK / SHOW UPI QR where admitted;
- DELIVERY / PICKUP when fulfilment requires shipping.

The user should see plain language first:
- Waiting for payment
- Payment confirmed
- Preparing shipment
- Carrier booked
- Picked up
- Out for delivery
- Delivered
- Delivery needs attention

Provider names and technical references are secondary unless operationally needed.

## Failure rules

If a carrier/payment provider is unavailable:
- preserve ECHO work;
- show the external action as not completed;
- retain retry/reconciliation state;
- never fabricate a shipment, payment or settlement;
- allow another admitted provider where business rules permit.

## WO-0013 boundary

This contract authorises only candidate design. No live external call, credential, shipment, payment, refund, NDR mutation or production admission is claimed under WO-0013.
