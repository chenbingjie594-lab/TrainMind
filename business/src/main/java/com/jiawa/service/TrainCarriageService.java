package com.jiawa.service;

import com.jiawa.domain.TrainCarriage;
import com.jiawa.req.TrainCarriageQueryReq;
import com.jiawa.req.TrainCarriageSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.TrainCarriageQueryResp;

import java.util.List;

public interface TrainCarriageService {
    void save(TrainCarriageSaveReq req);

    PageResp<TrainCarriageQueryResp> queryList(TrainCarriageQueryReq req);

    void delete(Long id);

    List<TrainCarriage> selectByTrainCode(String trainCode) ;
}