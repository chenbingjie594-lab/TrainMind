package com.jiawa.service;

import com.jiawa.domain.DailyTrainCarriage;
import com.jiawa.req.DailyTrainCarriageQueryReq;
import com.jiawa.req.DailyTrainCarriageSaveReq;
import com.jiawa.resp.DailyTrainCarriageQueryResp;
import com.jiawa.resp.PageResp;

import java.util.Date;
import java.util.List;

public interface DailyTrainCarriageService {
    void save(DailyTrainCarriageSaveReq req);

    PageResp<DailyTrainCarriageQueryResp> queryList(DailyTrainCarriageQueryReq req);

    void delete(Long id);

    void genDaily(Date date, String trainCode);

    List<DailyTrainCarriage> selectBySeatType (Date date, String trainCode, String seatType);
}