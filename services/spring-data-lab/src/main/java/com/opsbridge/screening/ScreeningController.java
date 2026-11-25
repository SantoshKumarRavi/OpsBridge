package com.opsbridge.screening;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/lab/v1/screenings")
public class ScreeningController {
    private final ScreeningService service;
    public ScreeningController(ScreeningService service) { this.service = service; }

    public record SimulateRequest(@NotBlank String subjectReference, boolean simulatedPepMatch, boolean simulatedSanctionsMatch) { }
    public record ScreeningView(String id, String subjectReference, String status, int simulatedRiskScore, String decisionReason, boolean simulation) {
        static ScreeningView from(ScreeningCase row) { return new ScreeningView(row.getId().toString(), row.getSubjectReference(), row.getStatus(), row.getSimulatedRiskScore(), row.getDecisionReason(), true); }
    }

    @GetMapping
    public List<ScreeningView> list(@RequestHeader("X-Tenant-Id") String tenantId) {
        return service.list(tenantId).stream().map(ScreeningView::from).toList();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ScreeningView create(@RequestHeader("X-Tenant-Id") String tenantId, @Valid @RequestBody SimulateRequest request) {
        return ScreeningView.from(service.simulate(tenantId, request.subjectReference(), request.simulatedPepMatch(), request.simulatedSanctionsMatch()));
    }
}
