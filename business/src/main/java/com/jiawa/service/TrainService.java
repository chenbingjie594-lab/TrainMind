package com.jiawa.service;

import com.jiawa.domain.Train;
import com.jiawa.req.TrainQueryReq;
import com.jiawa.req.TrainSaveReq;
import com.jiawa.resp.PageResp;
import com.jiawa.resp.TrainQueryResp;

import java.util.List;

public interface TrainService {
    void save(TrainSaveReq req);

    PageResp<TrainQueryResp> queryList(TrainQueryReq req);

    void delete(Long id);

    List<TrainQueryResp> queryAll();

    List<Train> selectAll();
}