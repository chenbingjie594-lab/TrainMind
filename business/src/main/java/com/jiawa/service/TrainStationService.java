package com.jiawa.service;

import com.jiawa.domain.TrainStation;
import com.jiawa.req.TrainStationQueryReq;
import com.jiawa.req.TrainStationSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.TrainStationQueryResp;

import java.util.List;

public interface TrainStationService {
    void save(TrainStationSaveReq req);

    PageResp<TrainStationQueryResp> queryList(TrainStationQueryReq req);

    void delete(Long id);

    List<TrainStation> selectByTrainCode(String trainCode);
}