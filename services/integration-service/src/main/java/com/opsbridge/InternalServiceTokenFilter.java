package com.opsbridge;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Component
public class InternalServiceTokenFilter extends OncePerRequestFilter {
    @Value("${opsbridge.security.internal-token:}") private String expectedToken;
    @Value("${APP_ENV:development}") private String appEnv;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return "/health".equals(path) || path.startsWith("/actuator/health") || path.startsWith("/actuator/prometheus");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if ("production".equals(appEnv)) {
            String supplied = request.getHeader("X-Internal-Service-Token");
            boolean valid = expectedToken != null && !expectedToken.isBlank() && supplied != null
                    && MessageDigest.isEqual(expectedToken.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8));
            if (!valid) {
                response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Trusted service context required.");
                return;
            }
        }
        chain.doFilter(request, response);
    }
}
