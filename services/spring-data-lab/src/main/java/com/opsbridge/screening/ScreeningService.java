package com.opsbridge.screening;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;

@Service
public class ScreeningService {
    private final ScreeningCaseRepository repository;
    public ScreeningService(ScreeningCaseRepository repository) { this.repository = repository; }

    @Transactional(readOnly = true)
    public List<ScreeningCase> list(String tenantId) { return repository.findTop50ByTenantIdOrderByCreatedAtDesc(tenantId); }

    @Transactional
    public ScreeningCase simulate(String tenantId, String subjectReference, boolean simulatedPepMatch, boolean simulatedSanctionsMatch) {
        int score = simulatedSanctionsMatch ? 100 : simulatedPepMatch ? 70 : 0;
        String status = score >= 70 ? "manual_review" : "no_simulated_match";
        String reason = simulatedSanctionsMatch ? "Synthetic sanctions flag; verify with an authorized screening provider."
                : simulatedPepMatch ? "Synthetic PEP flag; verify with an authorized screening provider."
                : "No simulated flags; this is not a real screening result.";
        return repository.save(new ScreeningCase(tenantId, subjectReference, status, score, reason));
    }
}
