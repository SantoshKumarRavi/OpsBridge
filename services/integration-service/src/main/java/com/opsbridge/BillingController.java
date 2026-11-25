package com.opsbridge;
import com.stripe.Stripe;
import com.stripe.exception.StripeException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.net.URI;
import java.util.*;
@RestController @RequestMapping("/api/v1/billing")
public class BillingController {
 @Value("${opsbridge.stripe.secret-key:}") private String stripeKey;
 @Value("${opsbridge.stripe.price-id:}") private String priceId;
 @Value("${opsbridge.stripe.allowed-return-origins}") private List<String> allowedOrigins;
 public record CheckoutRequest(@Email String email,@NotBlank String successUrl,@NotBlank String cancelUrl){}
 public record PortalRequest(@NotBlank String customerId,@NotBlank String returnUrl){}
 private void requireStripe(){if(stripeKey==null||stripeKey.isBlank()||priceId==null||priceId.isBlank())throw new IllegalStateException("Stripe sandbox credentials and a Price ID are required.");Stripe.apiKey=stripeKey;}
 private String allowUrl(String candidate){URI uri=URI.create(candidate);String origin=uri.getScheme()+"://"+uri.getAuthority();if(!"https".equalsIgnoreCase(uri.getScheme())&&!allowedOrigins.contains(origin))throw new IllegalArgumentException("Return URL origin is not allow-listed.");if(!allowedOrigins.contains(origin))throw new IllegalArgumentException("Return URL origin is not allow-listed.");return uri.toString();}
 @PostMapping("/checkout") public ResponseEntity<?> checkout(@Valid @RequestBody CheckoutRequest body,@RequestHeader("X-Tenant-Id") String tenant,@RequestHeader(value="Idempotency-Key",required=false) String idempotencyKey)throws StripeException{
  requireStripe();String key=idempotencyKey==null||idempotencyKey.isBlank()?UUID.randomUUID().toString():idempotencyKey;
  var params=com.stripe.param.checkout.SessionCreateParams.builder().setMode(com.stripe.param.checkout.SessionCreateParams.Mode.SUBSCRIPTION).setSuccessUrl(allowUrl(body.successUrl())).setCancelUrl(allowUrl(body.cancelUrl())).addLineItem(com.stripe.param.checkout.SessionCreateParams.LineItem.builder().setPrice(priceId).setQuantity(1L).build()).putMetadata("tenantId",tenant).setClientReferenceId(tenant);
  if(body.email()!=null&&!body.email().isBlank())params.setCustomerEmail(body.email());var options=com.stripe.net.RequestOptions.builder().setIdempotencyKey(key).build();var session=com.stripe.model.checkout.Session.create(params.build(),options);return ResponseEntity.ok(Map.of("id",session.getId(),"url",session.getUrl(),"provider","stripe","mode","subscription"));
 }
 @PostMapping("/portal") public ResponseEntity<?> portal(@Valid @RequestBody PortalRequest body,@RequestHeader("X-Tenant-Id") String tenant)throws StripeException{requireStripe();var params=com.stripe.param.billingportal.SessionCreateParams.builder().setCustomer(body.customerId()).setReturnUrl(allowUrl(body.returnUrl())).build();var session=com.stripe.model.billingportal.Session.create(params);return ResponseEntity.ok(Map.of("url",session.getUrl(),"provider","stripe","tenantId",tenant));}
}
