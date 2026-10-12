package com.jiawa.mapper.cust;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.Date;

@Mapper
public interface SkTokenMapperCust {

    int decrease(@Param("date") Date date, @Param("trainCode") String trainCode,@Param("decreaseCount") int decreaseCount);
}

