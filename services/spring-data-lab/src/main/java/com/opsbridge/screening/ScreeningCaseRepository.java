package com.opsbridge.screening;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface ScreeningCaseRepository extends JpaRepository<ScreeningCase, UUID> {
    List<ScreeningCase> findTop50ByTenantIdOrderByCreatedAtDesc(String tenantId);
}
