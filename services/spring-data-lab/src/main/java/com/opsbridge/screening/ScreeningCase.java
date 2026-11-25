package com.opsbridge.screening;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "screening_cases", indexes = @Index(name = "screening_tenant_created_idx", columnList = "tenant_id,created_at"))
public class ScreeningCase {
    @Id @GeneratedValue private UUID id;
    private String tenantId;
    private String subjectReference;
    private String status;
    private int simulatedRiskScore;
    private String decisionReason;
    private Instant createdAt;

    protected ScreeningCase() { }
    public ScreeningCase(String tenantId, String subjectReference, String status, int simulatedRiskScore, String decisionReason) {
        this.tenantId = tenantId; this.subjectReference = subjectReference; this.status = status;
        this.simulatedRiskScore = simulatedRiskScore; this.decisionReason = decisionReason; this.createdAt = Instant.now();
    }
    public UUID getId() { return id; }
    public String getTenantId() { return tenantId; }
    public String getSubjectReference() { return subjectReference; }
    public String getStatus() { return status; }
    public int getSimulatedRiskScore() { return simulatedRiskScore; }
    public String getDecisionReason() { return decisionReason; }
    public Instant getCreatedAt() { return createdAt; }
}
