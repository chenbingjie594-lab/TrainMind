package com.jiawa.agenttools.tool;

import com.jiawa.agenttools.config.ToolProperties;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class TicketReadTools {

    private final RestClient business;
    private final ToolProperties properties;

    public TicketReadTools(RestClient businessRestClient, ToolProperties properties) {
        this.business = businessRestClient;
        this.properties = properties;
    }

    @Tool(name = "search_stations",
            description = "按中文站名、拼音或拼音首字母搜索真实火车站。返回只读车站数据。")
    public Map<String, Object> searchStations(
            @ToolParam(description = "城市或车站关键词") String keyword) {
        Map<String, Object> response = get("/business/station/query-all", Map.of());
        List<Map<String, Object>> stations = contentList(response);
        String expected = keyword.toLowerCase(Locale.ROOT);
        List<Map<String, Object>> matched = stations.stream()
                .filter(station -> contains(station.get("name"), expected)
                        || contains(station.get("namePinyin"), expected)
                        || contains(station.get("namePy"), expected))
                .limit(properties.maxResults())
                .toList();
        return success(matched);
    }

    @Tool(name = "search_tickets",
            description = "查询真实车次和余票。日期必填；出发站和到达站可选，用于直达、邻近站或一次中转规划。")
    public Map<String, Object> searchTickets(
            @ToolParam(description = "出发日期，格式YYYY-MM-DD") String date,
            @ToolParam(description = "出发站名，可为空", required = false) String start,
            @ToolParam(description = "到达站名，可为空", required = false) String end) {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("page", 1);
        params.put("size", properties.maxResults());
        params.put("date", date);
        if (start != null && !start.isBlank()) {
            params.put("start", start);
        }
        if (end != null && !end.isBlank()) {
            params.put("end", end);
        }
        Map<String, Object> response =
                get("/business/daily-train-ticket/query-list", params);
        Object content = response.get("content");
        return success(content == null ? Collections.emptyMap() : content);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> get(String path, Map<String, Object> params) {
        return business.get()
                .uri(builder -> {
                    builder.path(path);
                    params.forEach((key, value) -> builder.queryParam(key, value));
                    return builder.build();
                })
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> contentList(Map<String, Object> response) {
        Object content = response == null ? null : response.get("content");
        return content instanceof List<?> list
                ? (List<Map<String, Object>>) list
                : List.of();
    }

    private static boolean contains(Object value, String expected) {
        return value != null
                && value.toString().toLowerCase(Locale.ROOT).contains(expected);
    }

    private static Map<String, Object> success(Object data) {
        return Map.of(
                "success", true,
                "code", "SUCCESS",
                "message", "ok",
                "data", data,
                "retryable", false
        );
    }
}
