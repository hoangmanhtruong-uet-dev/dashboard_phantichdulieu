package com.datainsight.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;
import java.util.*;

@RestController
@RequestMapping("/api/sales")
@CrossOrigin(origins = "*")
public class SalesController {

    private final String AI_SERVICE_URL = "http://localhost:8000";

    // 1. Endpoint Tải dữ liệu và lưu Database
    @PostMapping("/upload")
    public ResponseEntity<?> uploadData(@RequestParam("file") MultipartFile file) {
        // Logic: Đọc CSV -> Lưu vào PostgreSQL (Dùng JPA/Hibernate)
        // Hiện tại trả về thông báo thành công
        Map<String, String> response = new HashMap<>();
        response.put("message", "Đã lưu " + file.getOriginalFilename() + " vào Database thành công!");
        return ResponseEntity.ok(response);
    }

    // 2. Endpoint gọi AI để lấy dự báo
    @PostMapping("/ai-forecast")
    public ResponseEntity<?> getAIForecast(@RequestBody List<Map<String, Object>> salesHistory) {
        RestTemplate restTemplate = new RestTemplate();
        
        // Java đóng vai trò Proxy gọi sang Python AI Service
        ResponseEntity<Map> aiResponse = restTemplate.postForEntity(
            AI_SERVICE_URL + "/forecast", 
            salesHistory, 
            Map.class
        );
        
        return ResponseEntity.ok(aiResponse.getBody());
    }

    // 3. Endpoint lấy phân cụm khách hàng
    @PostMapping("/ai-cluster")
    public ResponseEntity<?> getCustomerClusters(@RequestBody List<Map<String, Object>> customerData) {
        RestTemplate restTemplate = new RestTemplate();
        
        ResponseEntity<Map> aiResponse = restTemplate.postForEntity(
            AI_SERVICE_URL + "/cluster", 
            customerData, 
            Map.class
        );
        
        return ResponseEntity.ok(aiResponse.getBody());
    }
}
