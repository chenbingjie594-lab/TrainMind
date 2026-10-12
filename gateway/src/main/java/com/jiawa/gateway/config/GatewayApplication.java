package com.jiawa.gateway.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.core.env.Environment;

import java.util.logging.Logger;

@SpringBootApplication
public class GatewayApplication {
    private static final Logger logger = Logger.getLogger(GatewayApplication.class.getName());

    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(GatewayApplication.class);
        Environment env = app.run(args).getEnvironment();
        logger.info("启动成功！");
        logger.info("网关地址：\thttp://127.0.0.1:"+env.getProperty("server.port"));
    }
}
