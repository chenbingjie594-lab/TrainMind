package com.jiawa.web;

import com.jiawa.resp.CommonResp;
import com.jiawa.resp.TrainQueryResp;
import com.jiawa.service.TrainService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/train")
public class WebTrainController {
    @Autowired
    private TrainService trainService;

    @GetMapping("/query-all")
    public CommonResp<List<TrainQueryResp>> queryList(){
        List<TrainQueryResp> list = trainService.queryAll();
        return new CommonResp<>(list);
    }

}