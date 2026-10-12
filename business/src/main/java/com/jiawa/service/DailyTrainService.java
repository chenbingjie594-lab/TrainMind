package com.jiawa.service;

import com.jiawa.req.DailyTrainQueryReq;
import com.jiawa.req.DailyTrainSaveReq;
import com.jiawa.resp.DailyTrainQueryResp;
import com.jiawa.resp.PageResp;

import java.util.Date;

public interface DailyTrainService {
    void save(DailyTrainSaveReq req);

    PageResp<DailyTrainQueryResp> queryList(DailyTrainQueryReq req);

    void delete(Long id);

    void genDaily(Date date);
}