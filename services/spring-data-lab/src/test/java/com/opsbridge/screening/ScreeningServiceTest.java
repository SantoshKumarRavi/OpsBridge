package com.opsbridge.screening;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ScreeningServiceTest {
    @Test
    void flagsAreAdvisoryAndRemainInManualReview() {
        ScreeningCase row = new ScreeningCase("demo", "synthetic-1", "manual_review", 100,
                "Synthetic sanctions flag; verify with an authorized screening provider.");
        assertEquals("manual_review", row.getStatus());
        assertEquals(100, row.getSimulatedRiskScore());
        assertTrue(row.getDecisionReason().contains("Synthetic"));
    }
}
