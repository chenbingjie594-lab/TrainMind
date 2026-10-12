package com.jiawa;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.core.env.Environment;

import java.util.logging.Logger;

@SpringBootApplication
public class  MemberApplication {
    private static final Logger logger = Logger.getLogger(MemberApplication.class.getName());

    public static void main(String[] args) {
        SpringApplication app = new SpringApplication(MemberApplication.class);
        Environment env = app.run(args).getEnvironment();
        logger.info("启动成功！");
        logger.info("测试地址：\thttp://localhost:8001"+"/member/?");
    }
}
