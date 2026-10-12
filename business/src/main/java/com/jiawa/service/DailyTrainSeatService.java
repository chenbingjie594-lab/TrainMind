package com.jiawa.service;

import com.jiawa.domain.DailyTrainSeat;
import com.jiawa.req.DailyTrainSeatQueryReq;
import com.jiawa.req.DailyTrainSeatSaveReq;
import com.jiawa.resp.DailyTrainSeatQueryResp;
import com.jiawa.resp.PageResp;

import java.util.Date;
import java.util.List;

public interface DailyTrainSeatService {
    void save(DailyTrainSeatSaveReq req);

    PageResp<DailyTrainSeatQueryResp> queryList(DailyTrainSeatQueryReq req);

    void delete(Long id);

    void genDaily(Date date, String trainCode);

    int countSeat(Date date, String trainCode, String seatType);

    List<DailyTrainSeat> selectByCarriage(Date date, String trainCode, Integer carriageIndex);
}