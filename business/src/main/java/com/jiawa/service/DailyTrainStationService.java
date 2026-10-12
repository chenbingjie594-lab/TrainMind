package com.jiawa.service;

import com.jiawa.req.DailyTrainStationQueryReq;
import com.jiawa.req.DailyTrainStationSaveReq;
import com.jiawa.resp.DailyTrainStationQueryResp;
import com.jiawa.resp.PageResp;

import java.util.Date;

public interface DailyTrainStationService {
    void save(DailyTrainStationSaveReq req);

    PageResp<DailyTrainStationQueryResp> queryList(DailyTrainStationQueryReq req);

    void delete(Long id);

    void genDaily(Date date, String trainCode);
}