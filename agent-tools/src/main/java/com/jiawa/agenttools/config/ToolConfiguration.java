package com.jiawa.agenttools.config;

import com.jiawa.agenttools.tool.TicketReadTools;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
public class ToolConfiguration {

    @Bean
    RestClient businessRestClient(RestClient.Builder builder, ToolProperties properties) {
        return builder.baseUrl(properties.businessBaseUrl()).build();
    }

    @Bean
    ToolCallbackProvider ticketToolCallbacks(TicketReadTools tools) {
        return MethodToolCallbackProvider.builder().toolObjects(tools).build();
    }
}
