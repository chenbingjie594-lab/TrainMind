package com.jiawa.agenttools.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "trainmind.tools")
public record ToolProperties(String businessBaseUrl, int maxResults) {
}
