package com.jiawa.service;

import com.jiawa.domain.TrainSeat;
import com.jiawa.req.TrainSeatQueryReq;
import com.jiawa.req.TrainSeatSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.TrainSeatQueryResp;

import java.util.List;

public interface TrainSeatService {
    void save(TrainSeatSaveReq req);

    PageResp<TrainSeatQueryResp> queryList(TrainSeatQueryReq req);

    void delete(Long id);

    void genTrainSeat(String trainCode);

    List<TrainSeat> selectByTrainCode(String trainCode);
}